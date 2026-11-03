import sys
from types import ModuleType

import pytest
import worker


def test_processor_disabled(monkeypatch):
    monkeypatch.delenv(
        "JOB_PROCESSOR",
        raising=False,
    )

    assert worker.load_processor() is None


def test_load_valid_processor(monkeypatch):
    fake = ModuleType("test_linesight_processor")

    fake.READY = True
    fake.MODEL_NAME = "test-detector"
    fake.MODEL_VERSION = "v1"

    fake.process_video = lambda path: {
        "findings": []
    }

    monkeypatch.setitem(
        sys.modules,
        fake.__name__,
        fake,
    )

    monkeypatch.setenv(
        "JOB_PROCESSOR",
        fake.__name__,
    )

    assert worker.load_processor() is fake


def test_reject_traversal(tmp_path, monkeypatch):
    (tmp_path / "videos").mkdir()

    (tmp_path / "secret.mp4").write_bytes(
        b"fake"
    )

    monkeypatch.setenv(
        "STORAGE_DIR",
        str(tmp_path),
    )

    with pytest.raises(FileNotFoundError):
        worker.get_video_path("../secret.mp4")


def test_no_job_returns_false(monkeypatch):
    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(
        worker,
        "new_session",
        Session,
    )

    monkeypatch.setattr(
        worker,
        "claim_next_job",
        lambda *args, **kwargs: None,
    )

    model = ModuleType("fake")
    model.MODEL_NAME = "test"
    model.MODEL_VERSION = "v1"

    assert worker.process_next_job(model) is False
