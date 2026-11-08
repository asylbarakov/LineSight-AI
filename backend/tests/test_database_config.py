"""Connection configuration regressions; no database/server required."""
import unittest
from urllib.parse import unquote, urlsplit

from app.config import Settings


class DatabaseConfiguration(unittest.TestCase):
    def settings(self, **values):
        return Settings.from_env({"SECRET_KEY": "test-only-signing-key-" * 3,
                                  "ADMIN_PASSWORD": "test-only-password", **values})

    def test_components_without_a_duplicate_database_url(self):
        url = self.settings(POSTGRES_USER="developer", POSTGRES_PASSWORD="test-password",
                            POSTGRES_DB="inspection_dev").database_url
        parts = urlsplit(url)
        self.assertEqual(parts.scheme, "postgresql+psycopg")
        self.assertEqual(parts.hostname, "postgres")
        self.assertEqual(parts.port, 5432)
        self.assertEqual(parts.username, "developer")
        self.assertEqual(parts.path, "/inspection_dev")

    def test_password_is_url_encoded_exactly_once(self):
        password = "test-only:@/#%$ +?"
        url = self.settings(POSTGRES_PASSWORD=password).database_url
        self.assertIsNotNone(urlsplit(url).password)
        self.assertEqual(unquote(urlsplit(url).password), password)

    def test_explicit_sqlite_url_keeps_existing_test_and_host_behavior(self):
        self.assertEqual(self.settings(DATABASE_URL="sqlite:///:memory:").database_url,
                         "sqlite:///:memory:")

    def test_explicit_external_url_remains_supported_outside_compose(self):
        url = "postgresql+psycopg://test-user:test-only@db.example.invalid:5433/test-db"
        self.assertEqual(self.settings(DATABASE_URL=url).database_url, url)

    def test_empty_url_in_compose_uses_shared_components(self):
        value = self.settings(DATABASE_URL="", POSTGRES_PASSWORD="test-only").database_url
        self.assertEqual(urlsplit(value).hostname, "postgres")

    def test_missing_password_and_invalid_port_fail_without_values(self):
        for values in ({"POSTGRES_HOST": "postgres"},
                       {"POSTGRES_PASSWORD": "private-test-value", "POSTGRES_PORT": "private-invalid"}):
            with self.subTest(values=list(values)):
                with self.assertRaises(ValueError) as error:
                    self.settings(**values)
                self.assertNotIn("private-test-value", str(error.exception))
                self.assertNotIn("private-invalid", str(error.exception))

    def test_no_postgres_settings_retains_local_sqlite_default(self):
        self.assertEqual(self.settings().database_url, "sqlite:///./linesight.db")


if __name__ == "__main__":
    unittest.main()
