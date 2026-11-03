"""Обработка одной инспекции воркером (задачи 43–44): статусы, коды ошибок, лимит времени.

НЕ ПРОВЕРЕНО в песочнице разработки (там нет SQLAlchemy): запустите `pytest backend/tests`.
"""

from __future__ import annotations

import contextlib
import logging
import signal
import threading
import time
import traceback
from typing import Callable

from sqlalchemy.orm import sessionmaker

from ml.config import PipelineConfig
from ml.errors import E_DECODE, E_MODEL, E_TIMEOUT, PipelineError
from ml.pipeline import PipelineResult, analyze_video

from . import repository as repo
from . import storage
from .config import Settings

log = logging.getLogger("linesight.worker")

AnalyzeFn = Callable[..., PipelineResult]


class _SoftTimeout(Exception):
    pass


@contextlib.contextmanager
def time_limit(seconds: int):
    """Лимит времени через SIGALRM. Работает только в главном потоке (как в воркере); иначе — без лимита."""
    usable = (
        seconds > 0
        and hasattr(signal, "SIGALRM")
        and threading.current_thread() is threading.main_thread()
    )
    if not usable:
        yield
        return

    def _handler(_signum, _frame):
        raise _SoftTimeout()

    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def classify_exception(exc: BaseException) -> tuple[str, str]:
    """Любое исключение → (код ошибки из контракта, сообщение)."""
    if isinstance(exc, PipelineError):
        return exc.code, exc.message
    if isinstance(exc, _SoftTimeout):
        return E_TIMEOUT, "Превышен лимит времени обработки"
    try:
        import cv2

        if isinstance(exc, cv2.error):
            return E_DECODE, f"Ошибка OpenCV при чтении видео: {exc}"
    except ImportError:  # pragma: no cover
        pass
    return E_MODEL, f"Внутренняя ошибка обработки: {type(exc).__name__}: {exc}"


def run_inspection(
    session_factory: sessionmaker,
    settings: Settings,
    inspection_id: str,
    cfg: PipelineConfig | None = None,
    analyze: AnalyzeFn = analyze_video,
    detector=None,
) -> bool:
    """Обрабатывает уже захваченную (`processing`) инспекцию. Возвращает True при успехе.

    Все ошибки превращаются в `failed` + код; наружу исключения не выходят.
    """
    cfg = cfg or PipelineConfig()
    out_dir = storage.inspection_dir(settings.data_dir, inspection_id)
    video = storage.video_path(settings.data_dir, inspection_id)
    started = time.perf_counter()
    last_progress = [0.0]

    def progress(p: float) -> None:
        now = time.monotonic()
        if now - last_progress[0] < 2.0:
            return
        last_progress[0] = now
        with session_factory() as s:
            repo.set_progress(s, inspection_id, p)

    kwargs = {"progress": progress}
    if detector is not None:
        kwargs["detector"] = detector

    log.info("[%s] старт обработки", inspection_id)
    try:
        with time_limit(settings.task_soft_time_limit_sec):
            result = analyze(str(video), str(out_dir), cfg, **kwargs)
        t_db = time.perf_counter()
        inputs = [
            repo.FindingInput(
                type=f.type,
                priority=f.priority,
                confidence=f.confidence,
                timecode_sec=f.timecode_sec,
                track_id=f.track_id,
                frame_path=f.frame_path,
                bbox=f.bbox,
            )
            for f in result.findings
        ]
        with session_factory() as s:
            repo.save_findings(s, inspection_id, inputs)
        stage_times = dict(result.stage_times)
        stage_times["db"] = round(time.perf_counter() - t_db, 3)
        with session_factory() as s:
            repo.mark_done(s, inspection_id, result.duration_sec, result.fps, stage_times)
        log.info(
            "[%s] готово: находок %s, %.1f кадр/с, всего %.1f с",
            inspection_id, len(inputs), result.fps, time.perf_counter() - started,
        )
        return True
    except BaseException as exc:  # noqa: BLE001 — нужно поймать и _SoftTimeout
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        code, message = classify_exception(exc)
        if not isinstance(exc, PipelineError):
            log.error("[%s] сбой: %s\n%s", inspection_id, message, traceback.format_exc())
        else:
            log.warning("[%s] ошибка %s: %s", inspection_id, code, message)
        with session_factory() as s:
            repo.mark_failed(s, inspection_id, code, message)
        return False
