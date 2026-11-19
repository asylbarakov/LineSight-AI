from pathlib import Path

from app import storage
from app.config import Settings


def test_volume_write_probe(monkeypatch, tmp_path):
    fake_settings = Settings(
        db_host="localhost",
        db_port=5432,
        db_name="linesight",
        db_user="linesight",
        db_password="dev",
        storage_dir=tmp_path,
    )
    monkeypatch.setattr(storage, "get_settings", lambda: fake_settings)
    assert storage.storage_writable()


def test_volume_write_probe_missing_path(monkeypatch, tmp_path):
    fake_settings = Settings(
        db_host="localhost",
        db_port=5432,
        db_name="linesight",
        db_user="linesight",
        db_password="dev",
        storage_dir=Path(tmp_path / "does-not-exist"),
    )
    monkeypatch.setattr(storage, "get_settings", lambda: fake_settings)
    assert not storage.storage_writable()
