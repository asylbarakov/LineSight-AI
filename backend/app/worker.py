"""Воркер: опрашивает таблицу `inspections` и обрабатывает задачи `queued` (очередь в Postgres).

Запуск: `python -m app.worker`

НЕ ПРОВЕРЕНО в песочнице разработки (там нет SQLAlchemy и Ultralytics).
"""

from __future__ import annotations

import logging
import signal
import time

from ml.config import PipelineConfig
from ml.detectors import make_detector
from ml.errors import PipelineError

from . import repository as repo
from .config import Settings
from .db import init_db, make_engine, make_session_factory
from .processing import run_inspection

log = logging.getLogger("linesight.worker")


class DetectorHolder:
    """Загружает детектор один раз на процесс и повторяет попытку, если весов ещё не было."""

    def __init__(self, cfg: PipelineConfig):
        self.cfg = cfg
        self._detector = None
        self._loaded = False

    def get(self):
        """Вернёт детектор или None (только «недостаточная видимость»). E_MODEL — если DETECTOR=yolo без весов."""
        if not self._loaded:
            self._detector = make_detector(self.cfg)  # может бросить PipelineError(E_MODEL)
            warm = getattr(self._detector, "warmup", None)
            if warm:
                warm()  # прогрев: первая обработка не тормозит
            self._loaded = True
            log.info("детектор загружен: %s", type(self._detector).__name__ if self._detector else "нет (auto без весов)")
        return self._detector


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings.from_env()
    cfg = PipelineConfig()
    engine = make_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)
    holder = DetectorHolder(cfg)

    with session_factory() as s:
        n = repo.fail_stale(s, older_than_sec=settings.task_soft_time_limit_sec * 2)
        if n:
            log.warning("помечено зависших задач: %s", n)

    # прогреваем модель заранее; если весов нет — не падаем, ошибка будет в задаче
    try:
        holder.get()
    except PipelineError as exc:
        log.warning("модель не загружена при старте (%s): %s", exc.code, exc.message)

    stop = {"flag": False}

    def _stop(_s, _f):
        stop["flag"] = True
        log.info("получен сигнал остановки, дорабатываю текущую задачу")

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    log.info("воркер запущен, опрос каждые %.1f с", settings.poll_interval_sec)
    while not stop["flag"]:
        with session_factory() as s:
            insp = repo.claim_next(s)
        if insp is None:
            time.sleep(settings.poll_interval_sec)
            continue
        try:
            detector = holder.get()
        except PipelineError as exc:
            with session_factory() as s:
                repo.mark_failed(s, insp.id, exc.code, exc.message)
            log.error("[%s] %s: %s", insp.id, exc.code, exc.message)
            continue
        run_inspection(session_factory, settings, insp.id, cfg=cfg, detector=detector if detector is not None else None)


if __name__ == "__main__":
    main()
