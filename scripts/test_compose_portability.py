"""Opt-in integration test: one isolated project, retained volumes, no production writes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Existing Backend runtime image; sources are mounted read-only")
    parser.add_argument("--project", default="linesight-portability-" + uuid.uuid4().hex[:8])
    parser.add_argument("--resume-dir", type=Path, help="Resume this script's own retained test project without resetting its volume")
    args = parser.parse_args()
    if not args.project.startswith("linesight-portability-"):
        parser.error("Use a new linesight-portability-* project, never an application project.")
    directory = args.resume_dir.resolve() if args.resume_dir else Path(tempfile.mkdtemp(prefix="linesight-portability-"))
    envfile, override = directory / "test.env", directory / "override.yml"
    values = {"POSTGRES_USER": "portability_user", "POSTGRES_DB": "portability_db",
              "POSTGRES_PASSWORD": "test-only:" + secrets.token_urlsafe(20) + ":$literal$$pair@#/% +",
              "ADMIN_LOGIN": "portability-admin", "ADMIN_PASSWORD": secrets.token_urlsafe(24),
              "SECRET_KEY": secrets.token_urlsafe(48), "DETECTOR": "none", "INSTALL_YOLO": "0",
              "DATABASE_URL": "postgresql://stale:unused@wrong-service/wrong-db",
              "API_PORT": "18463", "WEB_PORT": "18464"}
    if args.resume_dir:
        owned = subprocess.run(["docker", "inspect", args.project + "-api-1"], capture_output=True, text=True, timeout=15)
        if owned.returncode:
            parser.error("Cannot verify the retained test API owner.")
        item = json.loads(owned.stdout)[0]
        labels = item["Config"].get("Labels", {})
        configuration_files = labels.get("com.docker.compose.project.config_files", "").replace("\\", "/").lower()
        if labels.get("com.docker.compose.project") != args.project or str(override).replace("\\", "/").lower() not in configuration_files:
            parser.error("The retained environment does not belong to this test directory.")
        saved = dict(pair.split("=", 1) for pair in item["Config"]["Env"])
        for key in ("POSTGRES_USER", "POSTGRES_DB", "POSTGRES_PASSWORD", "ADMIN_LOGIN", "ADMIN_PASSWORD", "SECRET_KEY"):
            values[key] = saved[key]
    original_password = values["POSTGRES_PASSWORD"]
    environment = {k: v for k, v in os.environ.items() if k not in values and
                   k not in ("COMPOSE_PROJECT_NAME", "COMPOSE_FILE")}

    def run(command, phase, allow_failure=False):
        result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=150)
        if result.returncode and not allow_failure:
            # Raw Docker/config errors can contain resolved credentials.
            raise RuntimeError(f"{phase} failed (exit {result.returncode}); secret-bearing output suppressed.")
        return result

    def write_env():
        envfile.write_text("\n".join(f"{key}='{value}'" for key, value in values.items()) + "\n", encoding="utf-8")
        envfile.chmod(0o600)

    command = ["docker", "compose", "--project-directory", str(ROOT), "--project-name", args.project,
               "--env-file", str(envfile), "--file", str(ROOT / "docker-compose.yml"), "--file", str(override)]

    def compose(*parts, allow_failure=False):
        return run(command + list(parts), "Compose " + parts[0], allow_failure)

    def wait(service, healthy=True):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            identifier = compose("ps", "--all", "--quiet", service).stdout.strip()
            if identifier:
                state = json.loads(run(["docker", "inspect", identifier], "inspect").stdout)[0]["State"]
                if state.get("Health", {}).get("Status") == ("healthy" if healthy else "unhealthy"):
                    return identifier
            time.sleep(1)
        raise RuntimeError("Timed out waiting for isolated " + service)

    def preflight(check_db=True):
        result = run([sys.executable, str(ROOT / "scripts/preflight.py"), "--project", args.project,
                      "--env-file", str(envfile), "--file", str(ROOT / "docker-compose.yml"),
                      "--file", str(override)] + (["--check-db"] if check_db else []), "preflight", True)
        for secret in (original_password, values["POSTGRES_PASSWORD"], values["SECRET_KEY"], values["ADMIN_PASSWORD"]):
            if secret in result.stdout + result.stderr:
                raise RuntimeError("Preflight leaked a credential.")
        return result

    def api_metrics(total):
        code = ('import os,json,urllib.request; origin="http://127.0.0.1:8000"; '
                'body=json.dumps({"login":os.environ["ADMIN_LOGIN"],"password":os.environ["ADMIN_PASSWORD"]}).encode(); '
                'req=urllib.request.Request(origin+"/api/login",data=body,headers={"Content-Type":"application/json"}); '
                'token=json.load(urllib.request.urlopen(req))["token"]; '
                'req=urllib.request.Request(origin+"/api/metrics",headers={"Authorization":"Bearer "+token}); '
                'm=json.load(urllib.request.urlopen(req)); '
                f'assert (m["inspections_total"],m["detected_defects_total"],m["confirmed_defects_total"])==({total},0,0)')
        compose("exec", "-T", "api", "python", "-B", "-c", code)

    created = False
    try:
        projects = json.loads(run(["docker", "compose", "ls", "--all", "--format", "json"], "project inventory").stdout)
        exists = any(project["Name"] == args.project for project in projects)
        if exists and not args.resume_dir:
            raise RuntimeError("Test project already exists; do not reuse unknown data.")
        if args.resume_dir and not exists:
            raise RuntimeError("Cannot resume an absent test project.")
        volumes = run(["docker", "volume", "ls", "--format", "{{.Name}}"], "volume inventory").stdout.splitlines()
        if not args.resume_dir and any(name.startswith(args.project + "_") for name in volumes):
            raise RuntimeError("Test volumes already exist; do not overwrite them.")
        run(["docker", "image", "inspect", args.image], "runtime image")
        mounts = [{"type": "bind", "source": str(ROOT / "backend/app"), "target": "/srv/backend/app", "read_only": True},
                  {"type": "bind", "source": str(ROOT / "backend/tests"), "target": "/srv/backend/tests", "read_only": True},
                  {"type": "bind", "source": str(ROOT / "scripts"), "target": "/srv/scripts", "read_only": True},
                  {"type": "bind", "source": str(ROOT / "ml"), "target": "/srv/ml", "read_only": True},
                  {"type": "volume", "source": "media_data", "target": "/data"}]
        # !override removes application binds; no production model/media is mounted.
        block = json.dumps(mounts)
        override.write_text('services:\n  postgres:\n    healthcheck:\n      interval: 1s\n      timeout: 3s\n      retries: 2\n'
                            '  api:\n    image: ' + json.dumps(args.image) + '\n    ports: !reset []\n    volumes: !override ' + block + '\n'
                            '  worker:\n    image: ' + json.dumps(args.image) + '\n    volumes: !override ' + block + '\n', encoding="utf-8")
        write_env()
        for name, web, api in (("portability-alpha", "19404", "19400"), ("portability-beta", "19504", "19500")):
            config_env = {**environment, "WEB_PORT": web, "API_PORT": api}
            config = subprocess.run(["docker", "compose", "--project-name", name, "--env-file", str(envfile),
                                     "--file", str(ROOT / "docker-compose.yml"), "config", "--format", "json"],
                                    cwd=ROOT, env=config_env, capture_output=True, text=True, timeout=30)
            if config.returncode:
                raise RuntimeError("Independent project configuration failed.")
            data = json.loads(config.stdout)
            assert data["name"] == name
            assert data["volumes"]["pgdata"]["name"] == name + "_pgdata"
            assert data["networks"]["default"]["name"] == name + "_default"
            assert str(data["services"]["api"]["ports"][0]["published"]) == api
            assert str(data["services"]["web"]["ports"][0]["published"]) == web
        assert preflight(False).returncode == 0
        created = True
        compose("up", "-d", "--no-build", "--pull", "never", "postgres")
        postgres_id = wait("postgres")
        assert preflight().returncode == 0
        compose("up", "-d", "--no-build", "--pull", "never", "api", "worker")
        wait("api"); wait("worker")
        api_metrics(1 if args.resume_dir else 0)
        worker_check = ('from sqlalchemy import text; from app.config import Settings; '
                        'from app.db import make_engine; e=make_engine(Settings.from_env().database_url); '
                        'c=e.connect(); c.execute(text("BEGIN READ ONLY")); '
                        'assert c.execute(text("SELECT 1")).scalar()==1; c.rollback(); c.close(); e.dispose()')
        compose("exec", "-T", "worker", "python", "-B", "-c", worker_check)
        compose("exec", "-T", "api", "python", "-B", "-m", "unittest", "tests.test_database_config", "tests.test_preflight", "tests.test_dashboard_kpis", "-v")
        code = ('from app.config import Settings; from app.db import make_engine,make_session_factory,Inspection; '
                'e=make_engine(Settings.from_env().database_url); s=make_session_factory(e)(); '
                's.add(Inspection(id="portability-preserved",title="isolated test",filename="test-only.mp4",status="done")); '
                's.commit(); s.close(); e.dispose()')
        if not args.resume_dir:
            compose("exec", "-T", "api", "python", "-B", "-c", code)
        api_metrics(1)
        volume = json.loads(run(["docker", "inspect", postgres_id], "PG volume").stdout)[0]["Mounts"][0]["Name"]
        print(("Retained environment resumed without reset" if args.resume_dir else "Fresh install passed") +
              ": custom project/user/database, special-character password, API/worker, 22 unit regressions.", flush=True)
        compose("stop", "--timeout", "20", "api", "worker")
        values["POSTGRES_PASSWORD"] = "different-test-only-" + secrets.token_urlsafe(20)
        write_env()
        compose("up", "-d", "--no-build", "--pull", "never", "--no-deps", "postgres")
        changed_id = wait("postgres", healthy=False)
        changed = json.loads(run(["docker", "inspect", changed_id], "retained PG volume").stdout)[0]
        assert changed["Mounts"][0]["Name"] == volume
        # Readiness alone succeeds even though the configured password is wrong.
        compose("exec", "-T", "postgres", "pg_isready", "-U", values["POSTGRES_USER"], "-d", values["POSTGRES_DB"])
        assert preflight().returncode == 1
        print("Existing-volume mismatch correctly rejected without leaking credentials or resetting data.", flush=True)
        values["POSTGRES_PASSWORD"] = original_password
        write_env()
        compose("up", "-d", "--no-build", "--pull", "never", "--no-deps", "postgres")
        wait("postgres")
        assert preflight().returncode == 0
        compose("up", "-d", "--no-build", "--pull", "never", "api", "worker")
        wait("api"); wait("worker"); api_metrics(1)
        result = {"project": args.project, "fresh": "verified before resume" if args.resume_dir else "passed", "staleVolumePassword": "rejected",
                  "knownPasswordRecovery": "passed", "retainedTestInspections": 1,
                  "unitTests": 22, "volume": volume, "artifacts": str(directory)}
        (directory / "result.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)
        return 0
    except (RuntimeError, AssertionError, OSError, subprocess.TimeoutExpired) as error:
        location = traceback.extract_tb(error.__traceback__)[-1]
        reason = str(error) if type(error) is RuntimeError else type(error).__name__
        print(f"Portability validation failed at line {location.lineno}: {reason}. Production was not targeted.", file=sys.stderr)
        return 1
    finally:
        if created:
            compose("stop", "--timeout", "20", allow_failure=True)
        print("Isolated artifacts retained at " + str(directory) + "; volumes/containers are not deleted.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
