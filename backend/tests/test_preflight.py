"""Preflight must catch drift and never disclose login credentials."""
import copy
import subprocess
import unittest
from unittest.mock import patch

from scripts.preflight import check_database, validate_configuration, decode_compose_config


def configuration():
    pg = {"POSTGRES_USER": "test_user", "POSTGRES_DB": "test_db", "POSTGRES_PASSWORD": "private-fixture:@/$"}
    app = {**pg, "POSTGRES_HOST": "postgres", "POSTGRES_PORT": "5432", "DATABASE_URL": "",
           "SECRET_KEY": "fixture-signing-key-" * 3, "ADMIN_PASSWORD": "fixture-admin-password"}
    return {"services": {"postgres": {"environment": pg}, "api": {"environment": app},
                         "worker": {"environment": copy.deepcopy(app)}}}


class PreflightChecks(unittest.TestCase):
    def test_compose_serialized_dollars_are_decoded_once(self):
        import json
        config = configuration()
        password = "test-only:$literal$$pair:@/%"
        for service in config["services"].values():
            service["environment"]["POSTGRES_PASSWORD"] = password.replace("$", "$$")
        decoded = decode_compose_config(json.dumps(config))
        self.assertEqual(validate_configuration(decoded).password, password)

    def test_matching_services(self):
        self.assertEqual(validate_configuration(configuration()).database, "test_db")

    def test_drift_is_rejected_without_password_in_error(self):
        config = configuration()
        config["services"]["worker"]["environment"]["POSTGRES_PASSWORD"] = "other-private-value"
        with self.assertRaises(ValueError) as error:
            validate_configuration(config)
        self.assertNotIn("private", str(error.exception))

    def test_stale_duplicate_uri_is_detected(self):
        config = configuration()
        config["services"]["api"]["environment"]["DATABASE_URL"] = "postgresql://stale:secret@old-host/old-db"
        with self.assertRaisesRegex(ValueError, "Legacy DATABASE_URL"):
            validate_configuration(config)

    def test_placeholders_are_rejected(self):
        config = configuration()
        config["services"]["api"]["environment"]["SECRET_KEY"] = "change-me"
        with self.assertRaisesRegex(ValueError, "SECRET_KEY"):
            validate_configuration(config)

    @patch("scripts.preflight.subprocess.run")
    def test_tcp_check_passes_credentials_only_in_environment(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "1\n", "")
        connection = validate_configuration(configuration())
        check_database("test-container", connection)
        command = run.call_args.args[0]
        self.assertNotIn(connection.password, " ".join(command))
        # Official image permits localhost via trust: use service DNS, as clients do.
        self.assertEqual(command[command.index("-h") + 1], "postgres")
        self.assertEqual(run.call_args.kwargs["env"]["PGPASSWORD"], connection.password)

    @patch("scripts.preflight.subprocess.run")
    def test_server_errors_are_not_echoed(self, run):
        run.return_value = subprocess.CompletedProcess([], 2, "", "server included private-fixture:@/$")
        with self.assertRaises(ValueError) as error:
            check_database("test-container", validate_configuration(configuration()))
        self.assertNotIn("private-fixture", str(error.exception))


if __name__ == "__main__":
    unittest.main()
