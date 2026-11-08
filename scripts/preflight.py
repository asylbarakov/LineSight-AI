"""Read-only Compose configuration/TCP authentication checks; never print secrets."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.database_config import postgres_settings


def decode_compose_config(serialized):
    config = json.loads(serialized)
    # `compose config` escapes literal $ as $$ so its output can be reused as
    # a Compose file. The container receives a single $, not that serialization.
    for service in config.get("services", {}).values():
        service["environment"] = {
            key: value.replace("$$", "$") if isinstance(value, str) else value
            for key, value in service.get("environment", {}).items()
        }
    return config


def validate_configuration(config):
    services = config.get("services", {})
    postgres = services.get("postgres", {}).get("environment", {})
    expected = postgres_settings(postgres)
    for service in ("api", "worker"):
        env = services.get(service, {}).get("environment", {})
        actual = postgres_settings(env)
        if (actual.user, actual.password, actual.database) != (expected.user, expected.password, expected.database):
            raise ValueError("PostgreSQL credentials differ between services; check shared POSTGRES_* settings.")
        if actual.host != "postgres" or actual.port != 5432:
            raise ValueError("Compose clients must use service DNS postgres and internal port 5432.")
        legacy = env.get("DATABASE_URL", "")
        if legacy:
            try:
                parsed = urlsplit(legacy)
                matches = (parsed.scheme in ("postgresql", "postgresql+psycopg") and
                           (unquote(parsed.username or ""), unquote(parsed.password or ""),
                            parsed.path.lstrip("/"), parsed.hostname, parsed.port or 5432) ==
                           (actual.user, actual.password, actual.database, actual.host, actual.port))
            except ValueError:
                matches = False
            if not matches:
                raise ValueError("Legacy DATABASE_URL conflicts with POSTGRES_*; remove the duplicate or fix the local override.")
        if not env.get("SECRET_KEY") or env["SECRET_KEY"].startswith("change-me"):
            raise ValueError("Set a persistent random SECRET_KEY before starting the application.")
        if not env.get("ADMIN_PASSWORD") or env["ADMIN_PASSWORD"].startswith("change-me"):
            raise ValueError("Set your own ADMIN_PASSWORD before starting the application.")
    if expected.password.startswith("change-me"):
        raise ValueError("Set your own POSTGRES_PASSWORD; example credentials are placeholders.")
    return expected


def check_database(container, connection):
    # Values travel in the child environment, never command arguments or stdout.
    env = {**os.environ, "PGPASSWORD": connection.password, "PGUSER": connection.user,
           "PGDATABASE": connection.database, "PGCONNECT_TIMEOUT": "5"}
    command = ["docker", "exec", "-e", "PGPASSWORD", "-e", "PGUSER", "-e", "PGDATABASE",
               "-e", "PGCONNECT_TIMEOUT", container, "psql", "-h", connection.host, "-p", str(connection.port),
               "-XAtq", "-v", "ON_ERROR_STOP=1", "-c", "BEGIN READ ONLY; SELECT 1; ROLLBACK;"]
    try:
        result = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8", timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("Database authentication check could not complete; no data was changed.") from None
    if result.returncode or result.stdout.strip() != "1":
        raise ValueError("PostgreSQL login failed. Existing volumes retain their initial credentials. Follow the existing-volume recovery guide; do not reset the volume.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="Compose project name; use the same value for all commands")
    parser.add_argument("--env-file", help="Compose interpolation file (default: normal Compose .env rules)")
    parser.add_argument("--file", action="append", help="Explicit Compose file; repeat for a test/local override")
    parser.add_argument("--check-db", action="store_true", help="Authenticate read-only against the existing project PostgreSQL")
    args = parser.parse_args(argv)
    command = ["docker", "compose", "--project-directory", str(ROOT)]
    if args.project:
        command += ["--project-name", args.project]
    if args.env_file:
        command += ["--env-file", str(Path(args.env_file).resolve())]
    for file in args.file or []:
        command += ["--file", str(Path(file).resolve())]
    try:
        result = subprocess.run(command + ["config", "--format", "json"], capture_output=True, text=True, encoding="utf-8", timeout=30)
        if result.returncode:
            raise ValueError("Compose configuration could not be resolved. Check variable names and file syntax privately; raw errors are suppressed to protect secrets.")
        config = decode_compose_config(result.stdout)
        connection = validate_configuration(config)
        if args.check_db:
            found = subprocess.run(command + ["ps", "--status", "running", "--quiet", "postgres"], capture_output=True, text=True, encoding="utf-8", timeout=15)
            ids = found.stdout.split()
            if found.returncode or len(ids) != 1:
                raise ValueError("Start only this project's postgres service before running --check-db.")
            check_database(ids[0], connection)
        print("Preflight OK: shared database settings" + (" and read-only TCP authentication." if args.check_db else ". Database login has not been checked; use --check-db after postgres starts."))
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired):
        # ValueError messages above are fixed strings/variable names, never values.
        error = sys.exc_info()[1]
        message = str(error) if type(error) is ValueError else "Preflight could not complete; no data was changed."
        if isinstance(error, json.JSONDecodeError):
            message = "Compose returned invalid configuration JSON; raw output is suppressed."
        print("Preflight failed: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
