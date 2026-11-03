"""Детекторы: YOLO + ByteTrack (бой) и цветовой детектор для синтетических роликов (запасной).

Интерфейс: `begin()` перед новым видео, `process(frame) -> list[TrackedDetection]` на каждый кадр.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from .config import PipelineConfig
from .errors import E_MODEL, PipelineError
from .preprocess import FrameInfo
from .scoring import TrackedDetection
from .tracking import IoUTracker, RawDetection

BYTETRACK_YAML = str(Path(__file__).with_name("bytetrack.yaml"))


class Detector(Protocol):
    def begin(self) -> None: ...

    def process(self, frame: FrameInfo) -> list[TrackedDetection]: ...


class YoloDetector:
    """Ultralytics YOLO + ByteTrack.

    НЕ ПРОВЕРЕНО в песочнице разработки (там нет ultralytics/torch): проверьте на машине с GPU
    или в Colab/Kaggle командой `python -m ml.check_detector <weights> <video>`.
    """

    def __init__(self, model_path: str, conf: float = 0.25, device: str | None = None):
        if not os.path.isfile(model_path):
            raise PipelineError(E_MODEL, f"Файл весов не найден: {model_path}")
        try:
            from ultralytics import YOLO  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise PipelineError(E_MODEL, f"Не удалось импортировать ultralytics: {exc}") from exc
        try:
            self.model = YOLO(model_path)
        except Exception as exc:  # noqa: BLE001
            raise PipelineError(E_MODEL, f"Не удалось загрузить веса: {exc}") from exc
        self.conf = conf
        self.device = device
        self._first = True

    def warmup(self) -> None:
        """Один пустой инференс, чтобы первая обработка не тормозила (задача 51)."""
        blank = np.zeros((640, 640, 3), dtype=np.uint8)
        try:
            self.model.predict(blank, conf=self.conf, device=self.device, verbose=False)
        except Exception as exc:  # noqa: BLE001
            raise PipelineError(E_MODEL, f"Сбой прогрева модели: {exc}") from exc

    def begin(self) -> None:
        # первый вызов track() с persist=False сбрасывает состояние трекера
        self._first = True

    def process(self, frame: FrameInfo) -> list[TrackedDetection]:
        try:
            results = self.model.track(
                frame.image,
                persist=not self._first,
                tracker=BYTETRACK_YAML,
                conf=self.conf,
                device=self.device,
                verbose=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise PipelineError(E_MODEL, f"Сбой инференса: {exc}") from exc
        self._first = False
        if not results:
            return []
        boxes = results[0].boxes
        if boxes is None or boxes.id is None:
            return []
        names = results[0].names
        out: list[TrackedDetection] = []
        xyxyn = boxes.xyxyn.cpu().numpy()
        ids = boxes.id.int().cpu().tolist()
        confs = boxes.conf.cpu().tolist()
        classes = boxes.cls.int().cpu().tolist()
        for (x1, y1, x2, y2), tid, conf, cls in zip(xyxyn, ids, confs, classes):
            out.append(
                TrackedDetection(
                    track_id=int(tid),
                    class_name=str(names[int(cls)]),
                    confidence=float(conf),
                    bbox=(float(x1), float(y1), float(x2 - x1), float(y2 - y1)),
                )
            )
        return out


class SyntheticDetector:
    """Находит цветные фигуры из `make_synthetic` (опоры и изоляторы) через сегментацию цвета.

    Это запасной вариант для демо на синтетике («синтетика для демо» из рисков плана): он не
    обобщается на реальные видео.
    """

    # класс → (цвет BGR, мин. площадь рамки в долях кадра, мин. заполнение рамки)
    def __init__(self, tol: int = 28):
        from .make_synthetic import INSULATOR_BGR, TOWER_BGR

        self.targets = {
            "tower": (TOWER_BGR, 0.006, 0.12),
            "insulator": (INSULATOR_BGR, 0.0012, 0.6),
        }
        self.tol = tol
        self.tracker = IoUTracker()

    def begin(self) -> None:
        self.tracker = IoUTracker()

    def process(self, frame: FrameInfo) -> list[TrackedDetection]:
        img = frame.image
        h, w = img.shape[:2]
        raw: list[RawDetection] = []
        for name, (bgr, min_area, min_fill) in self.targets.items():
            lo = np.clip(np.array(bgr) - self.tol, 0, 255).astype(np.uint8)
            hi = np.clip(np.array(bgr) + self.tol, 0, 255).astype(np.uint8)
            mask = cv2.inRange(img, lo, hi)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                x, y, bw, bh = cv2.boundingRect(c)
                if bw * bh < min_area * w * h:
                    continue
                fill = cv2.contourArea(c) / max(1, bw * bh)
                if fill < min_fill:
                    continue
                raw.append(RawDetection(name, round(min(0.99, 0.5 + 0.5 * fill), 3), (x / w, y / h, bw / w, bh / h)))
        return self.tracker.update(raw)


def make_detector(cfg: PipelineConfig) -> Detector | None:
    """Выбирает детектор по `DETECTOR`: yolo | synthetic | none | auto (yolo, если есть веса)."""
    mode = cfg.detector.lower()
    if mode == "none":
        return None
    if mode == "synthetic":
        return SyntheticDetector()
    if mode == "auto":
        if not os.path.isfile(cfg.model_path):
            return None
        return YoloDetector(cfg.model_path, cfg.detect_conf)
    if mode == "yolo":
        return YoloDetector(cfg.model_path, cfg.detect_conf)
    raise PipelineError(E_MODEL, f"Неизвестный DETECTOR: {cfg.detector}")
