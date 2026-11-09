"""Installer safety contracts; temporary files and fake Docker, no live writes."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.linesight import (
    SetupError, prepare_env, choose_project, guard_volumes, schema_contract,
    changed_services, run_update,
    assignments,
)


TEMPLATE = "POSTGRES_PASSWORD=change-me-db-password\nADMIN_PASSWORD=change-me\nSECRET_KEY=change-me-key\nDETECTOR=none\nINSTALL_YOLO=0\n"


class InstallerContracts(unittest.TestCase):
    def test_ci_fixture_refuses_local_execution_before_any_docker_call(self):
        from scripts.verify_installer_ci import main
        with patch.dict(os.environ, {}, clear=True), patch("sys.argv", ["verify_installer_ci.py", "seed"]), patch("subprocess.run") as run:
            with self.assertRaisesRegex(SystemExit, "CI fixture refused"):
                main()
            run.assert_not_called()

    def test_existing_env_uses_compose_last_assignment_semantics(self):
        self.assertEqual(assignments("MODEL_PATH=first\nMODEL_PATH=second\n")["MODEL_PATH"], "second")

    def test_fresh_secrets_and_identity_are_generated_once(self):
        first = prepare_env(TEMPLATE, None, False, "linesight-test", weights=True)
        self.assertNotIn("change-me", first)
        self.assertIn("COMPOSE_PROJECT_NAME=linesight-test", first)
        self.assertIn("DETECTOR=yolo", first)
        self.assertIn("INSTALL_YOLO=1", first)
        self.assertEqual(first, prepare_env(TEMPLATE, first, False, "linesight-test", weights=True))

    def test_valid_existing_settings_are_not_rotated(self):
        original = "POSTGRES_PASSWORD='private:$#'\nADMIN_PASSWORD=existing-admin\nSECRET_KEY=existing-key\nCOMPOSE_PROJECT_NAME=existing\n"
        self.assertEqual(prepare_env(TEMPLATE, original, True, "existing"), original)

    def test_existing_storage_never_gets_new_secrets(self):
        with self.assertRaises(SetupError):
            prepare_env(TEMPLATE, TEMPLATE, True, "existing")
        with self.assertRaises(SetupError):
            prepare_env(TEMPLATE, None, True, "existing")

    def test_missing_model_requires_explicit_lightweight_mode(self):
        with self.assertRaises(SetupError):
            prepare_env(TEMPLATE, None, False, "test", weights=False)
        content = prepare_env(TEMPLATE, None, False, "test", weights=False, ml="none")
        self.assertIn("DETECTOR=none", content)

    def test_placeholder_copy_is_completed_only_before_storage_exists(self):
        content = prepare_env(TEMPLATE, TEMPLATE, False, "test", weights=True)
        self.assertNotIn("=change-me", content)
        self.assertIn("INSTALL_YOLO=1", content)

    def test_existing_ml_mode_is_preserved(self):
        original = prepare_env(TEMPLATE, None, False, "test", ml="none")
        self.assertEqual(prepare_env(TEMPLATE, original, True, "test", weights=True), original)
        with self.assertRaises(SetupError):
            prepare_env(TEMPLATE, original, True, "test", ml="yolo")

    def test_saved_project_survives_folder_rename(self):
        self.assertEqual(choose_project({"project": "saved"}, "saved", None, [], ["saved"]), "saved")

    def test_project_override_is_rejected_after_installation(self):
        with self.assertRaises(SetupError):
            choose_project({"project": "saved"}, "saved", "different", [], [])
        with self.assertRaises(SetupError):
            choose_project({"project": "saved"}, "different", None, [], [])

    def test_ambiguous_legacy_projects_stop_without_creating_another(self):
        with self.assertRaises(SetupError):
            choose_project(None, None, None, ["old", "new"], ["old", "new"])
        with self.assertRaises(SetupError):
            choose_project(None, None, None, [], ["linesight-old"])
        self.assertEqual(choose_project(None, None, "old", ["old", "new"], ["old", "new"]), "old")
        with self.assertRaises(SetupError):
            choose_project(None, None, "different", ["old"], ["old"])

    def test_missing_or_replaced_volume_is_not_recreated(self):
        saved = {"pgdata": {"name": "saved-pg", "created": "yesterday"}}
        for current in ({}, {"saved-pg": {"CreatedAt": "today"}}):
            with self.assertRaises(SetupError):
                guard_volumes(saved, current)
        guard_volumes(saved, {"saved-pg": {"CreatedAt": "yesterday"}})

    def test_schema_guard_ignores_comments_and_connection_helpers(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "db.py"
            path.write_text('class Inspection:\n __tablename__="inspections"\n id: int = 1\n')
            before = schema_contract(path)
            path.write_text(path.read_text() + '\n# comment\ndef connect(): return 2\n')
            self.assertEqual(schema_contract(path), before)
            path.write_text(path.read_text().replace('id: int = 1', 'id: int = 1\n extra: str = ""'))
            self.assertNotEqual(schema_contract(path), before)

    def test_only_changed_services_need_update(self):
        services = {s: {"State": {"Running": True, "Health": {"Status": "healthy"}}, "Image": "image", "Config": {"Labels": {"com.docker.compose.config-hash": "hash"}}} for s in ("api", "worker", "web")}
        self.assertEqual(changed_services(services, dict.fromkeys(services, "image"), dict.fromkeys(services, "hash")), [])
        services["web"]["Image"] = "older"
        self.assertEqual(changed_services(services, dict.fromkeys(services, "image"), dict.fromkeys(services, "hash")), ["web"])

    def test_unchanged_and_web_only_updates_do_not_stop_worker(self):
        events = []
        run_update([], {}, lambda *x: events.append(x), lambda: 0)
        run_update(["web"], {}, lambda *x: events.append(x), lambda: 0)
        self.assertEqual(events, [("up", "-d", "--no-deps", "--no-build", "web")])

    def test_active_jobs_block_worker_restart(self):
        events = []
        with self.assertRaises(SetupError):
            run_update(["worker"], {}, lambda *x: events.append(x), lambda: 1)
        self.assertEqual(events, [])

    def test_update_stops_writes_before_second_queue_check(self):
        events, counts = [], iter([0, 0])
        running = {"api": {"State": {"Running": True}}, "worker": {"State": {"Running": True}}}
        run_update(["api", "worker"], running, lambda *x: events.append(x), lambda: next(counts))
        self.assertEqual(events[0], ("stop", "--timeout", "900", "api"))
        self.assertEqual(events[1], ("stop", "--timeout", "1800", "worker"))
        self.assertEqual(events[2], ("up", "-d", "--no-deps", "--no-build", "api", "worker"))

    def test_job_arriving_during_cutover_restores_old_api(self):
        events, counts = [], iter([0, 1])
        running = {"api": {"State": {"Running": True}}}
        with self.assertRaises(SetupError):
            run_update(["worker"], running, lambda *x: events.append(x), lambda: next(counts))
        self.assertEqual(events, [("stop", "--timeout", "900", "api"), ("start", "api")])

    def test_queue_probe_failure_restores_api_before_propagating(self):
        events, probes = [], iter([0, RuntimeError("probe unavailable")])
        def active():
            value = next(probes)
            if isinstance(value, Exception): raise value
            return value
        with self.assertRaises(RuntimeError):
            run_update(["worker"], {"api": {"State": {"Running": True}}}, lambda *x: events.append(x), active)
        self.assertEqual(events, [("stop", "--timeout", "900", "api"), ("start", "api")])

    def test_api_only_update_keeps_unchanged_worker_running(self):
        events = []
        running = {s: {"State": {"Running": True}} for s in ("api", "worker")}
        run_update(["api"], running, lambda *x: events.append(x), lambda: 0)
        self.assertNotIn(("stop", "--timeout", "1800", "worker"), events)
