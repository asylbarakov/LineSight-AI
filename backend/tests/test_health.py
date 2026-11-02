from fastapi.testclient import TestClient
from app import main

client = TestClient(main.app)

def test_health_when_dependencies_ready(monkeypatch):
    monkeypatch.setattr(main, "ping_db", lambda: True)
    monkeypatch.setattr(main, "storage_writable", lambda: True)

    result = client.get("/health")
    assert result.status_code == 200
    assert result.json() == {
        "status": "ok",
        "service": "api",
        "database": "ok",
        "storage": "ok",
    }

def test_health_fails_if_database_unavailable(monkeypatch):
    monkeypatch.setattr(main, "ping_db", lambda: False)
    monkeypatch.setattr(main, "storage_writable", lambda: True)

    result = client.get("/health")
    assert result.status_code == 503
    assert result.json()["database"] == "unavailable"


def test_health_fails_if_storage_unavailable(monkeypatch):
    monkeypatch.setattr(main, "ping_db", lambda: True)
    monkeypatch.setattr(main, "storage_writable", lambda: False)

    result = client.get("/health")
    assert result.status_code == 503
    assert result.json()["storage"] == "unavailable"


def test_health_does_not_leak_db_errors(monkeypatch):
    def fail():
        raise RuntimeError("secret-password-should-not-leak")

    monkeypatch.setattr(main, "ping_db", fail)
    monkeypatch.setattr(main, "storage_writable", lambda: True)
    result = client.get("/health")
    assert result.status_code == 503
    assert "secret-password" not in result.text
