"""Тесты экспорта готовой инспекции и reset-demo."""

from app import demo, repository as repo, storage
from app.processing import run_inspection
from ml.config import PipelineConfig


def _make_done_inspection(session_factory, settings, video):
    import shutil
    iid = "11111111-1111-4111-8111-111111111111"
    out = storage.inspection_dir(settings.data_dir, iid)
    shutil.copy2(video, out / "video.mp4")
    with session_factory() as s:
        repo.create_inspection(s, iid, "Исходная", "blur.mp4", None)
        repo.claim_next(s)
    assert run_inspection(session_factory, settings, iid, cfg=PipelineConfig(detector="none"), detector=None)
    return iid


def test_export_import_and_reset(session_factory, settings, blur_video, tmp_path):
    iid = _make_done_inspection(session_factory, settings, blur_video)
    ddir = tmp_path / "demo"
    dest = demo.export_inspection(session_factory, settings, iid, ddir / demo.READY)
    assert (dest / "video.mp4").is_file() and (dest / "meta.json").is_file() and (dest / "findings.json").is_file()

    # на «грязной» системе reset оставляет ровно одну готовую инспекцию
    with session_factory() as s:
        repo.create_inspection(s, "22222222-2222-4222-8222-222222222222", "Мусор", "x.mp4", 1.0)
    new_id = demo.reset_demo(session_factory, settings, ddir)
    assert new_id is not None
    with session_factory() as s:
        rows = repo.list_inspections(s)
        assert len(rows) == 1
        insp, n = rows[0]
        assert insp.id == new_id and insp.status == "done" and insp.title == "Исходная" and n >= 1
        assert all(f.status == "new" for f in repo.list_findings(s, new_id))
    assert (storage.inspection_dir(settings.data_dir, new_id, create=False) / "video.mp4").is_file()


def test_reset_without_ready_inspection_just_clears(session_factory, settings, tmp_path):
    with session_factory() as s:
        repo.create_inspection(s, "33333333-3333-4333-8333-333333333333", "A", "a.mp4", 1.0)
    assert demo.reset_demo(session_factory, settings, tmp_path / "empty") is None
    with session_factory() as s:
        assert repo.list_inspections(s) == []
