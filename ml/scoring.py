"""Скоринг и сборка находок (задача 6).

Один трек даёт одну находку: максимальная уверенность, середина интервала как таймкод,
ключевой кадр — с лучшим сочетанием уверенности и резкости.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from .classes import is_defect
from .config import Thresholds
from .low_visibility import TYPE_LOW_VISIBILITY, LowVisInterval
from .preprocess import FrameInfo

PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"
PRIORITY_INSUFFICIENT = "insufficient_data"

# (x, y, w, h) в долях 0..1 от размера кадра, (x, y) — левый верхний угол
BBox = tuple[float, float, float, float]


@dataclass
class TrackedDetection:
    track_id: int
    class_name: str
    confidence: float
    bbox: BBox


@dataclass
class FindingData:
    type: str
    priority: str
    confidence: float
    timecode_sec: float
    track_id: int
    bbox: BBox | None = None
    key_image: np.ndarray | None = field(default=None, repr=False)
    frame_path: str | None = None  # заполняется при сохранении кадра


def compute_priority(class_name: str, confidence: float, duration_sec: float, th: Thresholds) -> str:
    """Приоритет находки.

    - уверенность ниже `min_confidence` → `insufficient_data`;
    - дефект: score = 0.7·conf + 0.3·min(1, длительность / duration_ref) → high / medium / low;
    - обычное оборудование (не дефект) — справочная находка с приоритетом `low`.
    """
    if confidence < th.min_confidence:
        return PRIORITY_INSUFFICIENT
    if not is_defect(class_name):
        return PRIORITY_LOW
    stability = min(1.0, max(0.0, duration_sec) / th.duration_ref_sec) if th.duration_ref_sec > 0 else 1.0
    score = 0.7 * confidence + 0.3 * stability
    if score >= th.high:
        return PRIORITY_HIGH
    if score >= th.medium:
        return PRIORITY_MEDIUM
    return PRIORITY_LOW


@dataclass
class _Track:
    track_id: int
    classes: Counter = field(default_factory=Counter)
    first_time: float = 0.0
    last_time: float = 0.0
    max_conf: float = 0.0
    observations: int = 0
    best_quality: float = -1.0
    best_image: np.ndarray | None = None
    best_bbox: BBox | None = None
    best_conf: float = 0.0


class TrackAggregator:
    """Копит наблюдения по трекам во время потоковой обработки кадров."""

    def __init__(self, step_sec: float, sharpness_ref: float, thresholds: Thresholds, max_image_width: int = 1280):
        self.step_sec = step_sec
        self.sharpness_ref = max(sharpness_ref, 1e-6)
        self.th = thresholds
        self.max_image_width = max_image_width
        self.tracks: dict[int, _Track] = {}

    def update(self, frame: FrameInfo, detections: list[TrackedDetection]) -> None:
        for det in detections:
            tr = self.tracks.get(det.track_id)
            if tr is None:
                tr = _Track(track_id=det.track_id, first_time=frame.time_sec)
                self.tracks[det.track_id] = tr
            tr.classes[det.class_name] += 1
            tr.last_time = frame.time_sec
            tr.max_conf = max(tr.max_conf, det.confidence)
            tr.observations += 1
            # лучший кадр: высокая уверенность и достаточная резкость
            quality = det.confidence * min(1.0, frame.sharpness / self.sharpness_ref)
            if quality > tr.best_quality:
                tr.best_quality = quality
                tr.best_image = _downscale(frame.image, self.max_image_width)
                tr.best_bbox = det.bbox
                tr.best_conf = det.confidence

    def to_findings(self) -> list[FindingData]:
        findings: list[FindingData] = []
        for tr in sorted(self.tracks.values(), key=lambda t: t.first_time):
            class_name = tr.classes.most_common(1)[0][0]
            duration = tr.last_time - tr.first_time + self.step_sec
            findings.append(
                FindingData(
                    type=class_name,
                    priority=compute_priority(class_name, tr.max_conf, duration, self.th),
                    confidence=round(tr.max_conf, 3),
                    timecode_sec=round((tr.first_time + tr.last_time) / 2, 3),
                    track_id=tr.track_id,
                    bbox=tr.best_bbox,
                    key_image=tr.best_image,
                )
            )
        return findings


def low_visibility_findings(intervals: list[LowVisInterval], max_image_width: int = 1280) -> list[FindingData]:
    """Интервалы плохой видимости → находки `low_visibility` (всегда `insufficient_data`)."""
    result = []
    for i, iv in enumerate(intervals):
        result.append(
            FindingData(
                type=TYPE_LOW_VISIBILITY,
                priority=PRIORITY_INSUFFICIENT,
                confidence=iv.confidence,
                timecode_sec=round(iv.start_sec, 3),
                track_id=i,
                bbox=None,
                key_image=_downscale(iv.key_image, max_image_width),
            )
        )
    return result


def _downscale(image: np.ndarray, max_width: int) -> np.ndarray:
    import cv2

    h, w = image.shape[:2]
    if w <= max_width:
        return image.copy()
    scale = max_width / w
    return cv2.resize(image, (max_width, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
