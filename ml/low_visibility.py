"""Находка «недостаточная видимость» (задача 4): работает без нейросети, по качеству кадров.

Кадр считается плохим, если он нерезкий (дисперсия лапласиана ниже порога) или тёмный
(средняя яркость ниже порога). Подряд идущие плохие кадры склеиваются в интервал; в находку
попадают интервалы не короче `min_sec`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .preprocess import FrameInfo

TYPE_LOW_VISIBILITY = "low_visibility"


@dataclass
class LowVisInterval:
    start_sec: float
    end_sec: float  # время последнего плохого кадра + шаг дискретизации
    kind: str  # blur | dark | blur+dark
    confidence: float  # 0..1
    key_time_sec: float
    key_index: int
    key_image: np.ndarray = field(repr=False)
    frames: int = 0

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec


def frame_severity(sharp: float, bright: float, sharp_min: float, bright_min: float) -> float:
    """Насколько кадр плох: 0 — в норме, 1 — совсем плохо."""
    sev_sharp = max(0.0, 1.0 - sharp / sharp_min) if sharp_min > 0 else 0.0
    sev_dark = max(0.0, 1.0 - bright / bright_min) if bright_min > 0 else 0.0
    return min(1.0, max(sev_sharp, sev_dark))


class LowVisibilityDetector:
    def __init__(self, sharpness_min: float, brightness_min: float, min_sec: float, step_sec: float):
        self.sharp_min = sharpness_min
        self.bright_min = brightness_min
        self.min_sec = min_sec
        self.step_sec = step_sec
        # допустимый разрыв между соседними плохими кадрами внутри одного интервала
        self._max_gap = step_sec * 1.5
        self._run: list[tuple[float, float, bool, bool]] = []  # время, severity, blur, dark (без изображений)
        self._worst: tuple[float, FrameInfo] | None = None
        self.intervals: list[LowVisInterval] = []

    def _close_run(self) -> None:
        if not self._run:
            return
        start = self._run[0][0]
        end = self._run[-1][0] + self.step_sec
        if end - start >= self.min_sec and self._worst is not None:
            blur = sum(1 for _, _, b, _d in self._run if b)
            dark = sum(1 for _, _, _b, d in self._run if d)
            n = len(self._run)
            if blur and dark and min(blur, dark) / n >= 0.25:
                kind = "blur+dark"
            else:
                kind = "dark" if dark > blur else "blur"
            mean_sev = sum(s for _, s, _, _ in self._run) / n
            worst = self._worst[1]
            self.intervals.append(
                LowVisInterval(
                    start_sec=start,
                    end_sec=end,
                    kind=kind,
                    confidence=round(min(1.0, 0.5 + 0.5 * mean_sev), 3),
                    key_time_sec=worst.time_sec,
                    key_index=worst.index,
                    key_image=worst.image,
                    frames=n,
                )
            )
        self._run = []
        self._worst = None

    def update(self, frame: FrameInfo) -> None:
        blur = frame.sharpness < self.sharp_min
        dark = frame.brightness < self.bright_min
        if not (blur or dark):
            self._close_run()
            return
        if self._run and frame.time_sec - self._run[-1][0] > self._max_gap:
            self._close_run()
        sev = frame_severity(frame.sharpness, frame.brightness, self.sharp_min, self.bright_min)
        self._run.append((frame.time_sec, sev, blur, dark))
        if self._worst is None or sev > self._worst[0]:
            self._worst = (sev, frame)

    def finish(self) -> list[LowVisInterval]:
        self._close_run()
        return self.intervals
