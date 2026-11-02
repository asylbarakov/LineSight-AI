from pathlib import Path

import worker

def test_storage_writable(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    assert worker.check_storage() is True

def test_storage_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "missing"))
    assert worker.check_storage() is False
