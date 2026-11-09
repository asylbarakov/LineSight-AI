"""Safe local setup/update. Standard library only; never reset an existing database."""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.preflight import check_database, decode_compose_config, validate_configuration


class SetupError(ValueError):
    pass


def assignments(text):
    result = {}
    for line in (text or "").splitlines():
        match = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=(.*)", line)
        if match:
            # Match Compose's last-assignment semantics without rewriting old envs.
            result[match[1]] = match[2].strip()
    return result


def literal(value):
    # Only used for literal project identity and recognizing empty/example values.
    value = value.strip()
    if value.startswith(("'", '"')) and value[-1:] == value[:1]:
        return value[1:-1]
    return value.split(" #", 1)[0].strip()


def replace_setting(text, key, value):
    pattern = re.compile(r"^\s*(?:export\s+)?" + re.escape(key) + r"\s*=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(lambda _: key + "=" + value, text)
    return text.rstrip() + "\n" + key + "=" + value + "\n"


def prepare_env(template, current, existing_storage, project, *, weights=True, ml=None):
    if current is None and existing_storage:
        raise SetupError("Existing data found but .env is missing. Restore its original configuration; no new credentials were generated.")
    text = template if current is None else current
    values = assignments(text)
    pristine = current is None or (not existing_storage and all(not literal(values.get(k, "")).strip() or literal(values.get(k, "")).startswith("change-me") for k in ("POSTGRES_PASSWORD", "ADMIN_PASSWORD", "SECRET_KEY")))
    for key in ("POSTGRES_PASSWORD", "ADMIN_PASSWORD", "SECRET_KEY"):
        value = literal(values.get(key, ""))
        if not value.strip() or value.startswith("change-me"):
            if existing_storage:
                raise SetupError("Existing data found: configure " + key + " using the recovery guide. Existing credentials were not replaced.")
            text = replace_setting(text, key, secrets.token_urlsafe(48 if key == "SECRET_KEY" else 24))
    saved_project = literal(values.get("COMPOSE_PROJECT_NAME", ""))
    if saved_project and saved_project != project:
        raise SetupError("COMPOSE_PROJECT_NAME conflicts with the saved deployment; refusing to select another database.")
    if not saved_project:
        text = replace_setting(text, "COMPOSE_PROJECT_NAME", project)
    if pristine or (not existing_storage and ml):
        mode = ml or "yolo"
        if mode == "yolo" and not weights:
            raise SetupError("Model weights are missing. Restore data/weights/best.pt or explicitly choose --ml none.")
        text = replace_setting(text, "DETECTOR", mode)
        text = replace_setting(text, "INSTALL_YOLO", "1" if mode == "yolo" else "0")
    elif ml and literal(values.get("DETECTOR", "none")) != ml:
        raise SetupError("Existing ML mode is preserved. Change DETECTOR/INSTALL_YOLO deliberately in .env before retrying.")
    return text


def choose_project(state, env_project, explicit, owned, known, *, allow_new=False):
    if state:
        project = state["project"]
        if any(value and value != project for value in (env_project, explicit)):
            raise SetupError("Project identity changed. Restore the saved COMPOSE_PROJECT_NAME; no new database will be created.")
    elif explicit or env_project:
        project = explicit or env_project
        if explicit and env_project and explicit != env_project:
            raise SetupError("--project conflicts with COMPOSE_PROJECT_NAME in .env.")
        if (owned or known) and project not in set(owned) | set(known) and not allow_new:
            raise SetupError("Selected project is new but older deployments/data exist. Use the existing identity, or --new only for an intentional separate installation.")
    elif len(owned) == 1:
        project = owned[0]
    elif owned or known:
        raise SetupError("Existing LineSight deployments/volumes found. Select the intended one with --adopt --project NAME; refusing to create another database.")
    else:
        project = "linesight-" + secrets.token_hex(4)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
        raise SetupError("Project name must be a literal lowercase Compose name.")
    return project


def guard_volumes(saved, current):
    for record in saved.values():
        actual = current.get(record["name"])
        if not actual or actual.get("CreatedAt") != record["created"]:
            raise SetupError("A saved data volume is missing or was replaced. Stop and recover the original volume; it will not be recreated empty.")


def validate_state(state):
    if (not isinstance(state, dict) or state.get("version") != 1 or
            not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", state.get("project", "")) or
            not isinstance(state.get("database"), str) or not state["database"] or
            not re.fullmatch(r"[a-f0-9]{64}", state.get("schema", "")) or
            not isinstance(state.get("postgres_image"), str) or
            not isinstance(state.get("volumes"), dict) or set(state["volumes"]) != {"pgdata", "media_data"}):
        raise SetupError("Deployment identity is invalid/incomplete. Restore .linesight from its backup; refusing to infer a new database.")
    for entry in state["volumes"].values():
        if not isinstance(entry, dict) or not entry.get("name") or not entry.get("created"):
            raise SetupError("Saved volume identity is incomplete; no empty replacement will be created.")


def schema_contract(path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    models = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and any(isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in stmt.targets) for stmt in node.body):
            models[node.name] = [ast.dump(stmt, include_attributes=False) for stmt in node.body if isinstance(stmt, (ast.Assign, ast.AnnAssign))]
    if not models:
        raise SetupError("Database model contract could not be identified.")
    return hashlib.sha256(json.dumps(models, sort_keys=True).encode()).hexdigest()


def changed_services(containers, images, hashes):
    changed = []
    for service in ("api", "worker", "web"):
        item = containers.get(service, {})
        status = item.get("State", {})
        if (not status.get("Running") or status.get("Health", {}).get("Status") != "healthy" or
                item.get("Image") != images[service] or
                item.get("Config", {}).get("Labels", {}).get("com.docker.compose.config-hash") != hashes[service]):
            changed.append(service)
    return changed


def run_update(changed, containers, compose, active_jobs):
    if not changed:
        return
    if "api" not in changed and "worker" not in changed:
        compose("up", "-d", "--no-deps", "--no-build", *changed)
        return
    if active_jobs():
        raise SetupError("Queued/processing inspections exist. Let the current Worker finish before updating; services were not stopped.")
    api_running = containers.get("api", {}).get("State", {}).get("Running", False)
    worker_running = containers.get("worker", {}).get("State", {}).get("Running", False) and "worker" in changed
    if api_running:
        # Give in-flight uploads time to finish; the second queue check catches them.
        compose("stop", "--timeout", "900", "api")
    try:
        if active_jobs():
            raise SetupError("A job arrived during the update. The old API was restored; retry after processing finishes.")
        if worker_running:
            compose("stop", "--timeout", "1800", "worker")
    except (Exception, KeyboardInterrupt):
        if api_running:
            compose("start", "api")
        raise
    # Restore quiesced services even if their image itself did not change.
    selected = [s for s in ("api", "worker", "web") if s in changed or (s == "api" and api_running) or (s == "worker" and worker_running)]
    compose("up", "-d", "--no-deps", "--no-build", *selected)


class Docker:
    def __init__(self, root):
        self.root = root
        self.env = dict(os.environ)
        # Explicit project/files/env win consistently on all developer machines.
        names = set(assignments((root / ".env.example").read_text(encoding="utf-8-sig")))
        if (root / ".env").exists():
            names.update(assignments((root / ".env").read_text(encoding="utf-8-sig")))
        for name in names | {"COMPOSE_PROJECT_NAME", "COMPOSE_FILE", "COMPOSE_PROFILES", "COMPOSE_ENV_FILES"}:
            self.env.pop(name, None)

    def call(self, *parts, allow_failure=False, timeout=60):
        try:
            result = subprocess.run(["docker", *parts], cwd=self.root, env=self.env, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise SetupError("Docker is unavailable or the operation timed out. Check Docker Engine/Desktop (Linux containers).") from None
        if result.returncode and not allow_failure:
            # Compose/config errors may contain resolved secrets: never echo them.
            raise SetupError("Docker operation failed (" + parts[0] + "). No data reset was attempted. Check Docker availability, registry access and your configuration privately.")
        return result

    def inspect(self, kind, names):
        if not names:
            return []
        return json.loads(self.call(kind, "inspect", *names).stdout)

    def inventory(self):
        ids = self.call("ps", "-aq", "--filter", "label=com.docker.compose.project").stdout.split()
        containers = self.inspect("container", ids)
        names = self.call("volume", "ls", "-q").stdout.split()
        volumes = {v["Name"]: v for v in self.inspect("volume", names)}
        return containers, volumes


def normalized(path):
    return str(path).replace("\\", "/").rstrip("/").casefold()


def compose_files(root):
    result = [root / "docker-compose.yml"]
    overrides = [root / name for name in ("docker-compose.override.yml", "docker-compose.override.yaml") if (root / name).exists()]
    if len(overrides) > 1:
        raise SetupError("Two local overrides found. Select a single maintained override before running setup.")
    return result + overrides


def command(root, project, envfile, files):
    return ["compose", "--project-directory", str(root), "--project-name", project,
            "--env-file", str(envfile), *[part for file in files for part in ("--file", str(file))]]


def resolve(docker, project, text, files, pin=None):
    with tempfile.TemporaryDirectory(prefix="linesight-config-") as directory:
        envfile = Path(directory) / "test.env"
        envfile.write_text(text, encoding="utf-8")
        envfile.chmod(0o600)
        selected = list(files)
        if pin:
            override = Path(directory) / "runtime.json"
            override.write_text(json.dumps(pin), encoding="utf-8")
            selected.append(override)
        result = docker.call(*command(docker.root, project, envfile, selected), "config", "--format", "json")
    return decode_compose_config(result.stdout)


def pin_configuration(state):
    return {"services": {"postgres": {"image": state["postgres_image"]}},
            "volumes": {role: {"name": entry["name"], "external": True} for role, entry in state["volumes"].items()}}


def private_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Exclusive temporary file + atomic replace, preserving existing credentials.
    temporary = path.with_name(path.name + ".writing")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        temporary.chmod(0o600)
        if os.name == "nt":
            identity = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", check=True)
            sid = next(csv.reader(identity.stdout.splitlines()))[1]
            if not re.fullmatch(r"S-1-[0-9-]+", sid):
                raise SetupError("Could not protect the local configuration file permissions.")
            subprocess.run(["icacls", str(temporary), "/inheritance:r", "/grant:r", "*" + sid + ":(F)",
                            "/grant:r", "*S-1-5-18:(F)"], capture_output=True, check=True)
        stream.write(text)
    os.replace(temporary, path)


def project_containers(items, project):
    selected = {}
    for item in items:
        labels = item["Config"].get("Labels", {})
        if labels.get("com.docker.compose.project") == project:
            service = labels.get("com.docker.compose.service")
            if service in selected:
                raise SetupError("Duplicate containers for a service. Resolve the deployment inventory before updating.")
            selected[service] = item
    return selected


def storage_names(config):
    result = {}
    for service, target, role in (("postgres", "/var/lib/postgresql/data", "pgdata"), ("api", "/data", "media_data"), ("worker", "/data", "media_data")):
        mounts = config["services"][service].get("volumes", [])
        mount = next((m for m in mounts if m["target"] == target), {})
        if mount.get("type") != "volume" or mount.get("source") != role:
            raise SetupError("Unsupported data mount. Setup requires the standard pgdata/media_data volumes; use the manual preservation guide for a custom deployment.")
        result[role] = config["volumes"][role]["name"]
    return result


def check_mounts(containers, names):
    for service, target, role in (("postgres", "/var/lib/postgresql/data", "pgdata"), ("api", "/data", "media_data"), ("worker", "/data", "media_data")):
        if service in containers:
            actual = next((m for m in containers[service]["Mounts"] if m["Destination"] == target), {})
            if actual.get("Name") != names[role]:
                raise SetupError("Running container data mount differs from the selected configuration. Restore the matching local override; refusing to switch databases/media.")


def check_ports(config, containers):
    seen = set()
    for service in ("api", "web"):
        item = containers.get(service, {})
        owned = item.get("HostConfig", {}).get("PortBindings", {}) if item.get("State", {}).get("Running") else {}
        for port in config["services"][service].get("ports", []):
            host, number = port.get("host_ip", "127.0.0.1"), int(port["published"])
            if number in seen:
                raise SetupError("API_PORT and WEB_PORT overlap; configure distinct unused ports in .env.")
            seen.add(number)
            if any(str(number) == p["HostPort"] and host == p["HostIp"] for entries in owned.values() for p in (entries or [])):
                continue
            try:
                with socket.socket() as probe:
                    probe.bind((host, number))
            except OSError:
                raise SetupError("A configured host port is unavailable. Choose unused API_PORT/WEB_PORT values in .env; setup will not stop another project.") from None


def wait_healthy(docker, container_id):
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        item = docker.inspect("container", [container_id])[0]
        if item["State"].get("Health", {}).get("Status") == "healthy":
            return
        if not item["State"].get("Running"):
            break
        time.sleep(2)
    raise SetupError("A service did not become healthy. Data and saved settings are retained; inspect that project's logs privately before retrying.")


def job_count(docker, container_id, connection, *, allow_missing=False):
    env = {**docker.env, "PGPASSWORD": connection.password, "PGUSER": connection.user, "PGDATABASE": connection.database, "PGCONNECT_TIMEOUT": "5"}
    def query(sql):
        result = subprocess.run(["docker", "exec", "-e", "PGPASSWORD", "-e", "PGUSER", "-e", "PGDATABASE", "-e", "PGCONNECT_TIMEOUT",
                             container_id, "psql", "-h", "postgres", "-XAtq", "-v", "ON_ERROR_STOP=1", "-c", sql],
                            env=env, capture_output=True, text=True, encoding="utf-8", timeout=15)
        if result.returncode or not result.stdout.strip().isdigit():
            raise SetupError("Could not verify the processing queue read-only. Update stopped before restarting the Worker.")
        return int(result.stdout.strip())
    if allow_missing and not query("BEGIN READ ONLY; SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='inspections'; ROLLBACK;"):
        return 0
    return query("BEGIN READ ONLY; SELECT count(*) FROM inspections WHERE status IN ('queued','processing'); ROLLBACK;")


def install(root, *, check=False, adopt=False, project=None, ml=None, new=False):
    docker = Docker(root)
    if docker.call("info", "--format", "{{.OSType}}").stdout.strip() != "linux":
        raise SetupError("Switch Docker Desktop to Linux containers before starting LineSight.")
    docker.call("compose", "version")
    statefile, runtimefile, envfile = root / ".linesight/deployment.json", root / ".linesight/compose.runtime.json", root / ".env"
    state = json.loads(statefile.read_text(encoding="utf-8")) if statefile.exists() else None
    if state:
        validate_state(state)
    current = envfile.read_text(encoding="utf-8-sig") if envfile.exists() else None
    values = assignments(current)
    if values.get("COMPOSE_FILE") or values.get("COMPOSE_PROFILES"):
        raise SetupError("Custom COMPOSE_FILE/COMPOSE_PROFILES needs a manual deployment review. Setup supports the base file and one local override.")
    items, volumes = docker.inventory()
    owned, known = set(), set()
    for item in items:
        labels = item["Config"].get("Labels", {})
        name = labels.get("com.docker.compose.project", "")
        if normalized(labels.get("com.docker.compose.project.working_dir", "")) == normalized(root):
            owned.add(name)
        if name.startswith("linesight"):
            known.add(name)
    for volume in volumes.values():
        name = (volume.get("Labels") or {}).get("com.docker.compose.project", "")
        if name.startswith("linesight"):
            known.add(name)
        elif volume["Name"].lower().startswith("linesight"):
            known.add("retained-unlabeled-data")
    selected = choose_project(state, literal(values.get("COMPOSE_PROJECT_NAME", "")), project, sorted(owned), sorted(known), allow_new=new or adopt)
    containers = project_containers(items, selected)
    existing = bool(state or containers or any((v.get("Labels") or {}).get("com.docker.compose.project") == selected for v in volumes.values()))
    if not state and existing and not (adopt or check):
        raise SetupError("Existing deployment found. First verify it with --check, then use --adopt --project " + selected + ". No secrets or volumes were changed.")
    text = prepare_env((root / ".env.example").read_text(encoding="utf-8-sig"), current, existing, selected,
                       weights=(root / "data/weights/best.pt").is_file(), ml=ml)
    files = compose_files(root)
    if state:
        guard_volumes(state["volumes"], volumes)
        if schema_contract(root / "backend/app/db.py") != state["schema"]:
            raise SetupError("Database model contract changed. A reviewed backup/migration is required before this update; no schema changes were applied.")
    config = resolve(docker, selected, text, files, pin_configuration(state) if state else None)
    connection = validate_configuration(config)
    if state and connection.database != state["database"]:
        raise SetupError("POSTGRES_DB differs from the saved database; refusing to switch inspection history.")
    names = storage_names(config)
    # External volumes are never synthesized, even on a first invocation.
    for role, name in names.items():
        if config["volumes"][role].get("external") and name not in volumes:
            raise SetupError("A configured external data volume is missing. Recover it; setup will not create a substitute.")
    if not state and any(name in volumes for name in names.values()):
        existing = True
        # Repeat the guard when an unlabeled external/legacy volume was discovered.
        text = prepare_env((root / ".env.example").read_text(encoding="utf-8-sig"), current, True, selected,
                           weights=(root / "data/weights/best.pt").is_file(), ml=ml)
        if not (adopt or check):
            raise SetupError("Existing data volume found. Use --check and explicit --adopt with the original .env.")
    if adopt and not existing:
        raise SetupError("No existing service/data volume matches the requested adoption. Refusing to initialize a new database instead.")
    check_mounts(containers, names)
    check_ports(config, containers)
    pg = containers.get("postgres")
    if pg and pg["State"].get("Running"):
        check_database(pg["Id"], connection)
    elif existing and check:
        raise SetupError("PostgreSQL is stopped. Read-only check will not start it; credentials have not been verified.")
    elif existing and not state:
        raise SetupError("First-time adoption requires the original PostgreSQL container to be running so credentials can be verified before recording state. Start that existing container and retry --check.")
    mode = config["services"]["worker"]["environment"]["DETECTOR"]
    if mode in ("yolo", "auto"):
        model = config["services"]["worker"]["environment"]["MODEL_PATH"]
        mount = next((m for m in config["services"]["worker"]["volumes"] if m["target"] == "/data/weights" and m["type"] == "bind"), None)
        if not mount or not model.startswith("/data/weights/") or not (Path(mount["source"]) / model.removeprefix("/data/weights/")).is_file():
            raise SetupError("YOLO model is unavailable in the configured read-only weights mount. Restore the file or explicitly select lightweight mode.")
        if str(config["services"]["worker"]["build"]["args"].get("INSTALL_YOLO")) != "1":
            raise SetupError("DETECTOR requires INSTALL_YOLO=1. Fix the existing .env; it was not rewritten.")
    if check:
        print("Check OK: " + ("existing database authenticated; data mounts match." if existing else "fresh configuration can be initialized.") + " No services or settings changed.")
        return
    if current != text:
        private_write(envfile, text)
    actual_files = list(files)
    if state:
        private_write(runtimefile, json.dumps(pin_configuration(state), indent=2))
        actual_files.append(runtimefile)
    base = command(root, selected, envfile, actual_files)
    def compose(*parts):
        return docker.call(*base, *parts, timeout=2400 if parts[0] == "build" else 1800)
    print("Building API, Worker and Frontend (cached layers are reused)...", flush=True)
    compose("build", "api", "worker", "web")
    if not existing:
        compose("create", "--no-build", "postgres", "api", "worker", "web")
    if not state:
        items, volumes = docker.inventory()
        containers = project_containers(items, selected)
        for role, name in names.items():
            if name not in volumes:
                raise SetupError("Required data volume missing after preparation. No replacement/reset was attempted.")
        pg = containers.get("postgres")
        if not pg:
            raise SetupError("Existing PostgreSQL container not found. Recover the original service before adoption.")
        image = docker.inspect("image", [pg["Image"]])[0]
        state = {"version": 1, "project": selected, "database": connection.database,
                 "schema": schema_contract(root / "backend/app/db.py"),
                 "postgres_image": next((r for r in image.get("RepoDigests", []) if r.startswith("postgres@")), pg["Image"]),
                 "volumes": {role: {"name": name, "created": volumes[name]["CreatedAt"]} for role, name in names.items()}}
        private_write(statefile, json.dumps(state, indent=2))
        private_write(runtimefile, json.dumps(pin_configuration(state), indent=2))
        actual_files.append(runtimefile)
        base = command(root, selected, envfile, actual_files)
    items, volumes = docker.inventory()
    guard_volumes(state["volumes"], volumes)
    containers = project_containers(items, selected)
    pg = containers.get("postgres")
    if pg:
        if not pg["State"].get("Running"):
            docker.call("start", pg["Id"])
    else:
        compose("up", "-d", "--no-deps", "--no-build", "postgres")
        containers = project_containers(docker.inventory()[0], selected)
        pg = containers["postgres"]
    # Retry authenticated SQL while a stopped/new PostgreSQL initializes.
    deadline = time.monotonic() + 120
    while True:
        try:
            check_database(pg["Id"], connection)
            break
        except ValueError:
            if time.monotonic() >= deadline:
                raise SetupError("PostgreSQL login failed. Existing volume passwords are unchanged; use the recovery guide. API/Worker were not deployed.") from None
            time.sleep(2)
    print("PostgreSQL authenticated. Checking application updates...", flush=True)
    # Hashes must be calculated with exactly the persisted Compose file selection.
    hashes = dict(line.split() for line in compose("config", "--hash", "*").stdout.splitlines())
    images = {}
    for service in ("api", "worker", "web"):
        tag = config["services"][service].get("image") or selected + "-" + service
        images[service] = docker.inspect("image", [tag])[0]["Id"]
    changed = changed_services(containers, images, hashes)
    if changed and existing and all(containers.get(s, {}).get("State", {}).get("Health", {}).get("Status") == "healthy" for s in ("api", "worker", "web")):
        rollback = {"services": {s: {"image": containers[s]["Image"]} for s in ("api", "worker", "web")}}
        private_write(root / ".linesight/rollback.json", json.dumps(rollback, indent=2))
    # Fresh services have no tables until API initializes: no queue to drain yet.
    active = (lambda: 0) if not existing else lambda: job_count(docker, pg["Id"], connection, allow_missing=not state.get("initialized", False))
    if not existing:
        # API creates the initial schema before Worker can inspect its queue.
        compose("up", "-d", "--no-deps", "--no-build", "api")
        api = project_containers(docker.inventory()[0], selected)["api"]
        wait_healthy(docker, api["Id"])
        compose("up", "-d", "--no-deps", "--no-build", "worker", "web")
    else:
        run_update(changed, containers, compose, active)
    containers = project_containers(docker.inventory()[0], selected)
    for service in ("api", "worker", "web"):
        wait_healthy(docker, containers[service]["Id"])
    state["initialized"] = True
    private_write(statefile, json.dumps(state, indent=2))
    port = config["services"]["web"]["ports"][0]["published"]
    print("Ready: http://localhost:" + str(port) + " (project " + selected + "). Login settings are in your local .env; do not share it.")
    if mode == "none":
        print("Lightweight mode: equipment detector is disabled; only capture-quality findings are available.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only validation; no services/files are changed")
    parser.add_argument("--adopt", action="store_true", help="Explicitly adopt an existing deployment without changing its secrets/data")
    parser.add_argument("--project", help="Existing project to adopt, or a name for a genuinely fresh installation")
    parser.add_argument("--ml", choices=("yolo", "none"), help="First install only; full YOLO is the default")
    parser.add_argument("--new", action="store_true", help="Explicit separate installation alongside other deployments; never changes a saved identity")
    args = parser.parse_args(argv)
    try:
        install(ROOT, check=args.check, adopt=args.adopt, project=args.project, ml=args.ml, new=args.new)
        return 0
    except (SetupError, ValueError, OSError, subprocess.TimeoutExpired):
        error = sys.exc_info()[1]
        message = str(error) if type(error) in (SetupError, ValueError) else "Setup could not complete. Existing data/settings are retained."
        if isinstance(error, json.JSONDecodeError):
            message = "Deployment state/configuration JSON is invalid; restore it before retrying."
        print("Setup stopped: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
