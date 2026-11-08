"""Database-backed KPI regressions; isolated SQLite, no shared records or ML execution."""
import unittest
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app import repository as repo
from app.db import Base, make_engine, make_session_factory


class DashboardKPIs(unittest.TestCase):
    def setUp(self):
        self.engine = make_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = make_session_factory(self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def counters(self):
        data = repo.metrics(self.session)
        return tuple(data.get(k) for k in ("inspections_total", "detected_defects_total", "confirmed_defects_total"))

    def inspection(self, iid="a"):
        return repo.create_inspection(self.session, iid, "Test", "test.mp4", None)

    def save(self, iid, *types):
        return repo.save_findings(self.session, iid, [repo.FindingInput(t, "insufficient_data" if t == "low_visibility" else "low", .8, i + .25, i) for i, t in enumerate(types)])

    def test_empty_database(self):
        self.assertEqual(self.counters(), (0, 0, 0))

    def test_confirmed_visibility_does_not_inflate_current_snapshot(self):
        # Reproduce the observed production distribution using isolated records.
        for iid in ("a", "b", "c", "d", "e"):
            self.inspection(iid)
        self.save("a", "czjyz_ps", "czjyz_ps", "low_visibility",
                  "low_visibility", "low_visibility", "yw", "yw")
        findings = repo.list_findings(self.session, "a")
        for finding_type in ("czjyz_ps", "low_visibility", "yw"):
            finding = next(f for f in findings if f.type == finding_type)
            repo.set_finding_status(self.session, finding.id, "confirmed")
        self.assertEqual(self.counters(), (5, 2, 1))

    def test_all_inspection_statuses_and_delayed_worker(self):
        self.inspection()
        self.assertEqual(self.counters(), (1, 0, 0))
        self.inspection("b")
        repo.mark_failed(self.session, "b", "E_MODEL", "test")
        self.save("a", "czjyz_ps")
        self.assertEqual(self.counters(), (2, 1, 0))
        processing = self.inspection("c")
        processing.status = "processing"
        self.session.commit()
        self.inspection("d")
        repo.mark_done(self.session, "d", 10, 30, {})
        self.assertEqual(self.counters(), (4, 1, 0))

    def test_visibility_equipment_unknown_and_errors_are_not_defects(self):
        self.inspection()
        self.save("a", "low_visibility", "insulator", "tower", "E_MODEL", "unknown", "yw", "nw", "foreign_object", "bird_nest")
        for f in repo.list_findings(self.session, "a"):
            repo.set_finding_status(self.session, f.id, "confirmed")
        self.assertEqual(self.counters(), (1, 0, 0))

    def test_multiple_types_and_idempotent_worker_save(self):
        self.inspection()
        self.save("a", "czjyz_ps", "yw", "nw", "Insulator damage", "insulator", "low_visibility")
        self.save("a", "czjyz_ps", "yw", "nw", "Insulator damage", "insulator", "low_visibility")
        self.inspection("b")
        self.save("b", "czjyz_ps")
        self.assertEqual(self.counters(), (2, 3, 0))

    def test_review_changes_recalculate_without_changing_detected(self):
        self.inspection()
        self.save("a", "czjyz_ps", "insulator_crack")
        f = repo.list_findings(self.session, "a")[0]
        for status, confirmed in [("confirmed", 1), ("confirmed", 1), ("rejected", 0), ("confirmed", 1), ("reshoot", 0)]:
            repo.set_finding_status(self.session, f.id, status)
            self.assertEqual(self.counters(), (1, 2, confirmed))

    def test_low_confidence_equipment_defect_is_still_a_candidate(self):
        self.inspection()
        repo.save_findings(self.session, "a", [repo.FindingInput("czjyz_ps", "insufficient_data", .2, 1, 1)])
        self.assertEqual(self.counters(), (1, 1, 0))
        f = repo.list_findings(self.session, "a")[0]
        repo.set_finding_status(self.session, f.id, "confirmed")
        self.assertEqual(self.counters(), (1, 1, 1))

    def test_authenticated_api_returns_fresh_committed_counts_after_review(self):
        from app.config import Settings
        from app.main import create_app
        with TemporaryDirectory() as directory:
            settings = Settings.from_env({"DATABASE_URL": f"sqlite:///{Path(directory) / 'isolated.db'}", "DATA_DIR": directory,
                                          "ADMIN_LOGIN": "test", "ADMIN_PASSWORD": "test", "SECRET_KEY": "x" * 40})
            app = create_app(settings)
            async def request(method, path, body=None, token=None):
                messages = []
                async def receive():
                    return {"type": "http.request", "body": json.dumps(body).encode() if body else b"", "more_body": False}
                async def send(message):
                    messages.append(message)
                headers = [(b"content-type", b"application/json")]
                if token:
                    headers.append((b"authorization", f"Bearer {token}".encode()))
                await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
                           "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"", "headers": headers,
                           "server": ("test", 80), "client": ("test", 123)}, receive, send)
                start = next(m for m in messages if m["type"] == "http.response.start")
                data = json.loads(b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body"))
                return start["status"], dict(start["headers"]), data
            try:
                self.assertEqual(asyncio.run(request("GET", "/api/metrics"))[0], 401)
                _, _, login = asyncio.run(request("POST", "/api/login", {"login": "test", "password": "test"}))
                token = login["token"]
                status, headers, data = asyncio.run(request("GET", "/api/metrics", token=token))
                self.assertEqual(status, 200)
                self.assertEqual(headers.get(b"cache-control"), b"no-store")
                self.assertEqual(data.get("detected_defects_total"), 0)
                with app.state.session_factory() as s:
                    repo.create_inspection(s, "api-test", "Test", "test.mp4", None)
                    repo.save_findings(s, "api-test", [repo.FindingInput("czjyz_ps", "high", .8, 1, 1)])
                    fid = repo.list_findings(s, "api-test")[0].id
                self.assertEqual(asyncio.run(request("PATCH", f"/api/findings/{fid}", {"status": "confirmed"}, token))[0], 200)
                _, _, data = asyncio.run(request("GET", "/api/metrics", token=token))
                self.assertEqual(tuple(data.get(k) for k in ("inspections_total", "detected_defects_total", "confirmed_defects_total")), (1, 1, 1))
            finally:
                app.state.engine.dispose()


if __name__ == "__main__":
    unittest.main()
