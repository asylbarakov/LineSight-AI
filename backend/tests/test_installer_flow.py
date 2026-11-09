"""End-to-end installer orchestration against an in-memory Docker engine."""
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import linesight as setup


class FakeDocker:
    def __init__(self, root):
        self.root, self.env = root, {}
        self.containers, self.volumes, self.events = {}, {}, []
        self.project = None
        self.fail_build = False

    def inventory(self):
        return copy.deepcopy(list(self.containers.values())), copy.deepcopy(self.volumes)

    def inspect(self, kind, names):
        if kind == "image":
            return [{"Id": "pg-image" if n.startswith(("pg-", "postgres")) else "new-" + n.rsplit("-", 1)[-1],
                     "RepoDigests": ["postgres@sha256:" + "a" * 64]} for n in names]
        return [copy.deepcopy(next(c for c in self.containers.values() if c["Id"] == n)) for n in names]

    def configuration(self, parts):
        envfile = Path(parts[parts.index("--env-file") + 1])
        env = {k: setup.literal(v) for k, v in setup.assignments(envfile.read_text()).items()}
        project = parts[parts.index("--project-name") + 1]
        self.project = project
        pg = {k: env.get(k, "linesight") for k in ("POSTGRES_USER", "POSTGRES_DB", "POSTGRES_PASSWORD")}
        shared = {**pg, **{k: env[k] for k in ("ADMIN_PASSWORD", "SECRET_KEY")}, "POSTGRES_HOST": "postgres", "POSTGRES_PORT": "5432", "DATABASE_URL": "",
                  "DETECTOR": env.get("DETECTOR", "none"), "MODEL_PATH": "/data/weights/best.pt"}
        config = {"name": project, "services": {}, "volumes": {r: {"name": project + "_" + r} for r in ("pgdata", "media_data")}}
        for s in ("postgres", "api", "worker", "web"):
            target, role = ("/var/lib/postgresql/data", "pgdata") if s == "postgres" else ("/data", "media_data")
            config["services"][s] = {"environment": pg if s == "postgres" else shared,
                                      "volumes": [{"type": "volume", "source": role, "target": target}], "ports": [],
                                      "build": {"args": {"INSTALL_YOLO": "0"}}}
        config["services"]["postgres"]["image"] = "postgres:16-alpine"
        config["services"]["web"]["ports"] = [{"published": "19404", "target": 3000}]
        for i, part in enumerate(parts[:-1]):
            if part == "--file" and parts[i + 1].endswith(".json"):
                pin = json.loads(Path(parts[i + 1]).read_text())
                config["volumes"].update(pin.get("volumes", {}))
                for service, values in pin.get("services", {}).items():
                    config["services"][service].update(values)
        return config

    def create(self, project):
        self.project = project
        for r in ("pgdata", "media_data"):
            name = project + "_" + r
            self.volumes.setdefault(name, {"Name": name, "CreatedAt": "original", "Labels": {"com.docker.compose.project": project}})
        for s in ("postgres", "api", "worker", "web"):
            role = "pgdata" if s == "postgres" else "media_data"
            self.containers.setdefault(s, {"Id": s + "-id", "Image": "pg-image" if s == "postgres" else "new-" + s,
                "State": {"Running": False, "Health": {"Status": "healthy"}},
                "Config": {"Labels": {"com.docker.compose.project": project, "com.docker.compose.service": s,
                                       "com.docker.compose.project.working_dir": str(self.root), "com.docker.compose.config-hash": "hash-" + s}},
                "Mounts": [{"Name": project + "_" + role, "Destination": "/var/lib/postgresql/data" if s == "postgres" else "/data"}]})

    def call(self, *parts, **kwargs):
        output = ""
        if parts[0] == "info": output = "linux"
        elif parts[0] == "compose" and parts[1] == "version": output = "v2"
        elif parts[0] == "start":
            self.events.append(parts)
            for c in self.containers.values():
                if c["Id"] == parts[1]: c["State"]["Running"] = True
        elif parts[0] == "compose":
            if "config" in parts:
                if "--hash" in parts: output = "\n".join(s + " hash-" + s for s in ("api", "worker", "web", "postgres"))
                else: output = json.dumps(self.configuration(parts))
            elif "build" in parts:
                self.events.append(("build",))
                if self.fail_build: raise setup.SetupError("Simulated build failure")
            elif "create" in parts:
                self.events.append(("create",))
                self.create(parts[parts.index("--project-name") + 1])
            elif "up" in parts:
                self.events.append(("up",))
                for s in ("api", "worker", "web", "postgres"):
                    if s in parts:
                        self.containers[s]["State"]["Running"] = True
                        self.containers[s]["Image"] = "pg-image" if s == "postgres" else "new-" + s
            elif "stop" in parts:
                self.events.append(("stop",))
                self.containers[parts[-1]]["State"]["Running"] = False
        return subprocess.CompletedProcess(parts, 0, output, "")


class InstallerFlow(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "backend/app").mkdir(parents=True)
        (self.root / "backend/app/db.py").write_text('class Inspection:\n __tablename__="inspections"\n id: int = 1\n')
        (self.root / ".env.example").write_text('POSTGRES_USER=linesight\nPOSTGRES_DB=linesight\nPOSTGRES_PASSWORD=change-me\nADMIN_PASSWORD=change-me\nSECRET_KEY=change-me\nDETECTOR=none\nINSTALL_YOLO=0\n')
        (self.root / "docker-compose.yml").write_text("# fake fixture")
        self.docker = FakeDocker(self.root)
        self.output = io.StringIO()
        for name, value in [("Docker", lambda root: self.docker), ("check_ports", lambda *args: None), ("check_database", lambda *args: None), ("job_count", lambda *args, **kwargs: 0)]:
            p = patch.object(setup, name, value); p.start(); self.addCleanup(p.stop)
        p = contextlib.redirect_stdout(self.output); p.__enter__(); self.addCleanup(p.__exit__, None, None, None)

    def run_install(self, **kwargs):
        setup.install(self.root, **kwargs)

    def test_fresh_then_repeat_retains_env_volumes_and_postgres(self):
        self.run_install(ml="none")
        env = (self.root / ".env").read_bytes()
        state = json.loads((self.root / ".linesight/deployment.json").read_text())
        volumes = copy.deepcopy(self.docker.volumes)
        self.docker.events.clear()
        self.run_install()
        self.assertEqual((self.root / ".env").read_bytes(), env)
        self.assertEqual(self.docker.volumes, volumes)
        self.assertEqual(self.docker.events, [("build",)])
        self.assertTrue(state["initialized"])
        for key in ("SECRET_KEY", "POSTGRES_PASSWORD", "ADMIN_PASSWORD"):
            self.assertNotIn(setup.literal(setup.assignments(env.decode())[key]), self.output.getvalue())

    def test_fresh_check_creates_no_files_or_resources(self):
        self.run_install(check=True, ml="none")
        self.assertFalse((self.root / ".env").exists())
        self.assertFalse((self.root / ".linesight").exists())
        self.assertFalse(self.docker.events)

    def test_failed_build_does_not_create_services_and_retry_keeps_secrets(self):
        self.docker.fail_build = True
        with self.assertRaises(setup.SetupError): self.run_install(ml="none")
        env = (self.root / ".env").read_bytes()
        self.assertFalse(self.docker.volumes)
        self.docker.fail_build = False
        self.run_install()
        self.assertEqual((self.root / ".env").read_bytes(), env)

    def test_missing_saved_volume_stops_before_build(self):
        self.run_install(ml="none")
        self.docker.volumes.pop(self.docker.project + "_pgdata")
        self.docker.events.clear()
        with self.assertRaises(setup.SetupError): self.run_install()
        self.assertFalse(self.docker.events)

    def test_schema_change_stops_before_build(self):
        self.run_install(ml="none")
        with (self.root / "backend/app/db.py").open("a") as f: f.write(' extra: str = ""\n')
        self.docker.events.clear()
        with self.assertRaises(setup.SetupError): self.run_install()
        self.assertFalse(self.docker.events)

    def test_legacy_requires_adoption_and_authentication_before_build(self):
        self.docker.create("linesight-old")
        for c in self.docker.containers.values(): c["State"]["Running"] = True
        content = setup.prepare_env((self.root / ".env.example").read_text(), None, False, "linesight-old", ml="none")
        (self.root / ".env").write_text(content)
        with self.assertRaises(setup.SetupError): self.run_install()
        with patch.object(setup, "check_database", side_effect=ValueError("PostgreSQL login failed")):
            with self.assertRaises(ValueError): self.run_install(adopt=True)
        self.assertFalse(self.docker.events)
        self.assertFalse((self.root / ".linesight").exists())
        self.assertEqual((self.root / ".env").read_text(), content)
        self.run_install(adopt=True)
        self.assertTrue((self.root / ".linesight/deployment.json").is_file())
        self.assertEqual(self.docker.events, [("build",)])

    def test_rename_keeps_saved_identity_despite_old_container_directory(self):
        self.run_install(ml="none")
        saved = self.docker.project
        for c in self.docker.containers.values(): c["Config"]["Labels"]["com.docker.compose.project.working_dir"] = "/previous/folder"
        self.docker.events.clear()
        self.run_install()
        self.assertEqual(self.docker.project, saved)
        self.assertEqual(self.docker.events, [("build",)])

    def test_unlabeled_legacy_volume_does_not_trigger_empty_installation(self):
        self.docker.volumes["linesight-old_pgdata"] = {"Name": "linesight-old_pgdata", "CreatedAt": "original", "Labels": None}
        with self.assertRaises(setup.SetupError): self.run_install(ml="none")
        self.assertFalse((self.root / ".env").exists())
        self.assertFalse(self.docker.events)
