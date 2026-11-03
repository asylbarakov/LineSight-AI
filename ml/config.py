"""Настройки пайплайна. Значения по умолчанию можно переопределить через .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _s(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Thresholds:
    """Пороги скоринга находок (задача 6). Подбираются в задаче 9."""

    # объект или дефект, увиденный хуже этого порога, считается «недостаточно данных»
    min_confidence: float = 0.35
    # длительность трека, после которой он считается «устойчивым», секунды
    duration_ref_sec: float = 2.0
    # границы приоритета для дефектов по score = 0.7*conf + 0.3*min(1, длительность/ref)
    high: float = 0.75
    medium: float = 0.50


@dataclass(frozen=True)
class PipelineConfig:
    frame_step_sec: float = field(default_factory=lambda: _f("FRAME_STEP_SEC", 0.5))
    detect_conf: float = field(default_factory=lambda: _f("DETECT_CONF", 0.25))
    model_path: str = field(default_factory=lambda: _s("MODEL_PATH", "/data/weights/best.pt"))
    # auto | yolo | synthetic | none. auto: YOLO, если файл весов есть, иначе только
    # «недостаточная видимость». yolo без весов даёт E_MODEL.
    detector: str = field(default_factory=lambda: _s("DETECTOR", "auto"))
    sharpness_min: float = field(default_factory=lambda: _f("SHARPNESS_MIN", 60.0))
    brightness_min: float = field(default_factory=lambda: _f("BRIGHTNESS_MIN", 50.0))
    low_vis_min_sec: float = field(default_factory=lambda: _f("LOW_VIS_MIN_SEC", 2.0))
    # максимальная ширина сохраняемого ключевого кадра
    keyframe_max_width: int = 1280
    thresholds: Thresholds = field(default_factory=Thresholds)
