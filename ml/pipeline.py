"""Пайплайн обработки видео: кадры → детекция и трекинг → находки → ключевые кадры (на диск)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cv2

from .classes import normalize
from .config import PipelineConfig
from .detectors import Detector, make_detector
from .errors import E_DECODE, PipelineError
from .low_visibility import LowVisibilityDetector
from .preprocess import iter_frames, probe_video
from .scoring import FindingData, TrackAggregator, low_visibility_findings

_DEFAULT = "default"


@dataclass
class PipelineResult:
    findings: list[FindingData]
    duration_sec: float
    fps: float  # обработанных кадров в секунду работы пайплайна
    frames_processed: int
    stage_times: dict[str, float] = field(default_factory=dict)


def analyze_video(
    video_path: str,
    out_dir: str,
    cfg: PipelineConfig | None = None,
    detector: Detector | None | str = _DEFAULT,
    progress: Callable[[float], None] | None = None,
) -> PipelineResult:
    """Обрабатывает видео и сохраняет ключевые кадры в `out_dir/frames/`.

    `detector`: по умолчанию выбирается из настроек (`DETECTOR`), `None` — без детекции
    (остаётся только «недостаточная видимость»).
    """
    cfg = cfg or PipelineConfig()
    t_total = time.perf_counter()
    meta = probe_video(video_path)
    if detector == _DEFAULT:
        detector = make_detector(cfg)

    low_vis = LowVisibilityDetector(cfg.sharpness_min, cfg.brightness_min, cfg.low_vis_min_sec, cfg.frame_step_sec)
    aggregator = TrackAggregator(cfg.frame_step_sec, cfg.sharpness_min, cfg.thresholds, cfg.keyframe_max_width)
    if detector is not None:
        detector.begin()

    times = {"decode": 0.0, "detect": 0.0, "track": 0.0, "findings": 0.0}
    frames = 0
    expected = max(1, int(meta.duration_sec / cfg.frame_step_sec))

    frame_iter = iter_frames(video_path, cfg.frame_step_sec)
    while True:
        t0 = time.perf_counter()
        frame = next(frame_iter, None)
        times["decode"] += time.perf_counter() - t0
        if frame is None:
            break
        frames += 1

        t0 = time.perf_counter()
        low_vis.update(frame)
        detections = detector.process(frame) if detector is not None else []
        times["detect"] += time.perf_counter() - t0

        t0 = time.perf_counter()
        aggregator.update(frame, detections)
        times["track"] += time.perf_counter() - t0

        if progress is not None and frames % 5 == 0:
            progress(min(0.99, frames / expected))

    if frames == 0:
        raise PipelineError(E_DECODE, "Не удалось прочитать ни одного кадра")

    t0 = time.perf_counter()
    findings = aggregator.to_findings() + low_visibility_findings(low_vis.finish(), cfg.keyframe_max_width)
    findings.sort(key=lambda f: f.timecode_sec)
    _save_keyframes(findings, Path(out_dir))
    times["findings"] = time.perf_counter() - t0

    work = times["decode"] + times["detect"] + times["track"]
    times["total"] = time.perf_counter() - t_total
    return PipelineResult(
        findings=findings,
        duration_sec=round(meta.duration_sec, 3),
        fps=round(frames / work, 2) if work > 0 else 0.0,
        frames_processed=frames,
        stage_times={k: round(v, 3) for k, v in times.items()},
    )


def _save_keyframes(findings: list[FindingData], out_dir: Path) -> None:
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for f in findings:
        if f.key_image is None:
            continue
        prefix = "lv" if f.type == "low_visibility" else normalize(f.type)
        name = f"{prefix}_{f.track_id}.jpg"
        cv2.imwrite(str(frames_dir / name), f.key_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        f.frame_path = f"frames/{name}"
        f.key_image = None  # освобождаем память
