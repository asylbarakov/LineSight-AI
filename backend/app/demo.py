"""Демо-данные: экспорт готовой инспекции и `reset-demo` (задачи 39, 63, 65).

Команды (из каталога backend/ или в контейнере api):
    python -m app.demo build <video.mp4> [название]   # обработать видео и сохранить как готовую инспекцию
    python -m app.demo export <inspection_id>         # выгрузить уже обработанную инспекцию
    python -m app.demo reset                          # очистить всё и загрузить готовую инспекцию

Готовая инспекция лежит в `<DEMO_DIR>/ready_inspection/`: `meta.json`, `findings.json`, `video.mp4`, `frames/`.

НЕ ПРОВЕРЕНО в песочнице разработки (нет SQLAlchemy): покрыто тестом `backend/tests/test_demo.py`.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from datetime import timedelta
from pathlib import Path

from ml.config import PipelineConfig

from . import repository as repo
from . import storage
from .config import Settings
from .db import init_db, make_engine, make_session_factory, new_id, utcnow

log = logging.getLogger("linesight.demo")

READY = "ready_inspection"


def demo_dir(settings: Settings) -> Path:
    return Path(os.environ.get("DEMO_DIR") or Path(settings.data_dir) / "demo")


def export_inspection(session_factory, settings: Settings, inspection_id: str, dest: Path) -> Path:
    """Выгружает инспекцию (видео, кадры, находки) в каталог `dest`."""
    with session_factory() as s:
        insp = repo.get_inspection(s, inspection_id)
        if insp is None:
            raise ValueError(f"Инспекция не найдена: {inspection_id}")
        findings = repo.list_findings(s, inspection_id)
        meta = {
            "title": insp.title,
            "filename": insp.filename,
            "duration_sec": insp.duration_sec,
            "fps": insp.fps,
            "stage_times": insp.stage_times,
        }
        rows = [
            {
                "type": f.type, "priority": f.priority, "confidence": f.confidence,
                "timecode_sec": f.timecode_sec, "frame_path": f.frame_path, "track_id": f.track_id,
                "bbox": None if f.bbox_x is None else [f.bbox_x, f.bbox_y, f.bbox_w, f.bbox_h],
            }
            for f in findings
        ]
    src = storage.inspection_dir(settings.data_dir, inspection_id, create=False)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copy2(src / "video.mp4", dest / "video.mp4")
    if (src / "frames").is_dir():
        shutil.copytree(src / "frames", dest / "frames")
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (dest / "findings.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


def import_inspection(session_factory, settings: Settings, src: Path) -> str:
    """Загружает готовую инспекцию из каталога (формат — как у `export_inspection`). Возвращает id."""
    meta = json.loads((src / "meta.json").read_text(encoding="utf-8"))
    rows = json.loads((src / "findings.json").read_text(encoding="utf-8"))
    iid = new_id()
    dest = storage.inspection_dir(settings.data_dir, iid)
    shutil.copy2(src / "video.mp4", dest / "video.mp4")
    if (src / "frames").is_dir():
        shutil.copytree(src / "frames", dest / "frames", dirs_exist_ok=True)
    now = utcnow()
    with session_factory() as s:
        repo.create_inspection(s, iid, meta["title"], meta.get("filename") or "video.mp4", meta.get("duration_sec"))
        repo.mark_done(s, iid, meta.get("duration_sec") or 0.0, meta.get("fps") or 0.0, meta.get("stage_times") or {})
        insp = repo.get_inspection(s, iid)
        total = float((meta.get("stage_times") or {}).get("total") or 1.0)
        insp.started_at = now - timedelta(seconds=total)
        insp.finished_at = now
        s.commit()
        inputs = [
            repo.FindingInput(
                type=r["type"], priority=r["priority"], confidence=r["confidence"],
                timecode_sec=r["timecode_sec"], track_id=r["track_id"], frame_path=r.get("frame_path"),
                bbox=tuple(r["bbox"]) if r.get("bbox") else None,
            )
            for r in rows
        ]
        repo.save_findings(s, iid, inputs)
    return iid


def clear_all(session_factory, settings: Settings) -> int:
    """Удаляет все инспекции и их папки. Возвращает число удалённых."""
    with session_factory() as s:
        ids = [i.id for i, _ in repo.list_inspections(s)]
        for iid in ids:
            repo.delete_inspection(s, iid)
    for iid in ids:
        storage.delete_inspection_dir(settings.data_dir, iid)
    return len(ids)


def reset_demo(session_factory, settings: Settings, ddir: Path | None = None) -> str | None:
    """Возвращает систему к состоянию «готово к показу». id готовой инспекции или None, если её нет."""
    ddir = ddir or demo_dir(settings)
    removed = clear_all(session_factory, settings)
    log.info("удалено инспекций: %s", removed)
    ready = ddir / READY
    if not (ready / "meta.json").is_file():
        log.warning("готовая инспекция не найдена: %s (выполните `python -m app.demo build <video>`)", ready)
        return None
    iid = import_inspection(session_factory, settings, ready)
    log.info("загружена готовая инспекция %s", iid)
    return iid


def build_ready(session_factory, settings: Settings, video: Path, title: str, ddir: Path | None = None) -> Path:
    """Обрабатывает видео пайплайном и сохраняет результат как готовую инспекцию."""
    from .processing import run_inspection

    ddir = ddir or demo_dir(settings)
    iid = new_id()
    out = storage.inspection_dir(settings.data_dir, iid)
    shutil.copy2(video, out / "video.mp4")
    cfg = PipelineConfig()
    from ml.detectors import make_detector

    detector = make_detector(cfg)
    with session_factory() as s:
        repo.create_inspection(s, iid, title, video.name, None)
        repo.claim_next(s)
    ok = run_inspection(session_factory, settings, iid, cfg=cfg, detector=detector)
    if not ok:
        raise RuntimeError("Обработка не удалась, см. логи")
    dest = export_inspection(session_factory, settings, iid, ddir / READY)
    repo_cleanup = os.environ.get("DEMO_KEEP", "0") != "1"
    if repo_cleanup:
        with session_factory() as s:
            repo.delete_inspection(s, iid)
        storage.delete_inspection_dir(settings.data_dir, iid)
    return dest


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in {"reset", "export", "build"}:
        print(__doc__)
        return 2
    settings = Settings.from_env()
    engine = make_engine(settings.database_url)
    init_db(engine)
    sf = make_session_factory(engine)
    cmd = argv[0]
    if cmd == "reset":
        reset_demo(sf, settings)
    elif cmd == "export":
        dest = export_inspection(sf, settings, argv[1], demo_dir(settings) / READY)
        print(f"Выгружено в {dest}")
    else:
        title = argv[2] if len(argv) > 2 else "Демо-инспекция"
        dest = build_ready(sf, settings, Path(argv[1]), title)
        print(f"Готовая инспекция сохранена в {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
