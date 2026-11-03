"""Предобработка видео: чтение кадров с шагом, резкость, яркость, таймкоды (задача 57)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterator

import cv2
import numpy as np

from .errors import E_DECODE, E_VIDEO_INVALID, PipelineError

# Ширина, к которой приводим кадр перед подсчётом резкости, чтобы значения
# не зависели от разрешения видео.
METRIC_WIDTH = 640


@dataclass(frozen=True)
class VideoMeta:
    fps: float
    frame_count: int
    width: int
    height: int

    @property
    def duration_sec(self) -> float:
        return self.frame_count / self.fps if self.fps > 0 else 0.0


@dataclass
class FrameInfo:
    index: int  # номер кадра в исходном видео
    time_sec: float  # index / fps
    sharpness: float  # дисперсия лапласиана
    brightness: float  # средняя яркость серого, 0..255
    image: np.ndarray  # BGR, исходное разрешение


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def sharpness(image: np.ndarray) -> float:
    """Резкость: дисперсия лапласиана серого кадра, приведённого к ширине METRIC_WIDTH."""
    gray = _to_gray(image)
    h, w = gray.shape[:2]
    if w > METRIC_WIDTH:
        scale = METRIC_WIDTH / w
        gray = cv2.resize(gray, (METRIC_WIDTH, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def brightness(image: np.ndarray) -> float:
    """Средняя яркость кадра, 0..255."""
    return float(_to_gray(image).mean())


def probe_video(path: str) -> VideoMeta:
    """Открывает видео и читает метаданные. Не открылось — E_VIDEO_INVALID."""
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise PipelineError(E_VIDEO_INVALID, "Файл не открывается как видео")
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        cap.release()
    if not math.isfinite(fps) or fps <= 0 or count <= 0 or width <= 0 or height <= 0:
        raise PipelineError(E_VIDEO_INVALID, "В видео нет корректных метаданных (fps, размер, число кадров)")
    return VideoMeta(fps=fps, frame_count=count, width=width, height=height)


def iter_frames(path: str, step_sec: float) -> Iterator[FrameInfo]:
    """Отдаёт кадры примерно каждые `step_sec` секунд.

    Лишние кадры пропускаются через `grab()` без декодирования. Если не удалось прочитать
    ни одного кадра — E_DECODE.
    """
    if step_sec <= 0:
        raise ValueError("step_sec должен быть положительным")
    meta = probe_video(path)
    step = max(1, int(round(step_sec * meta.fps)))

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise PipelineError(E_VIDEO_INVALID, "Файл не открывается как видео")
    produced = 0
    index = 0
    try:
        while True:
            if index % step == 0:
                ok, image = cap.read()
                if not ok:
                    break
                produced += 1
                yield FrameInfo(
                    index=index,
                    time_sec=index / meta.fps,
                    sharpness=sharpness(image),
                    brightness=brightness(image),
                    image=image,
                )
            else:
                if not cap.grab():
                    break
            index += 1
    finally:
        cap.release()
    if produced == 0:
        raise PipelineError(E_DECODE, "Не удалось прочитать ни одного кадра")
