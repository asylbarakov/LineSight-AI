"""Простой IoU-трекер.

Основной трекер в бою — ByteTrack из Ultralytics (см. `detectors.YoloDetector`). Этот трекер
нужен для детекторов без собственного трекинга (синтетический детектор) и для юнит-тестов:
он проверяет правило «один объект — один трек».
"""

from __future__ import annotations

from dataclasses import dataclass

from .scoring import BBox, TrackedDetection


@dataclass(frozen=True)
class RawDetection:
    class_name: str
    confidence: float
    bbox: BBox  # (x, y, w, h) в долях 0..1


def iou(a: BBox, b: BBox) -> float:
    ax2, ay2 = a[0] + a[2], a[1] + a[3]
    bx2, by2 = b[0] + b[2], b[1] + b[3]
    iw = max(0.0, min(ax2, bx2) - max(a[0], b[0]))
    ih = max(0.0, min(ay2, by2) - max(a[1], b[1]))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def similarity(a: BBox, b: BBox) -> float:
    """IoU, а для рамки, обрезанной краем кадра, — ещё и доля вложенности (inter / меньшая площадь)."""
    score = iou(a, b)
    ax2, ay2 = a[0] + a[2], a[1] + a[3]
    bx2, by2 = b[0] + b[2], b[1] + b[3]
    iw = max(0.0, min(ax2, bx2) - max(a[0], b[0]))
    ih = max(0.0, min(ay2, by2) - max(a[1], b[1]))
    smaller = min(a[2] * a[3], b[2] * b[3])
    contain = (iw * ih) / smaller if smaller > 0 else 0.0
    return max(score, 0.8 * contain if contain >= 0.7 else 0.0)


@dataclass
class _State:
    track_id: int
    class_name: str
    bbox: BBox
    missed: int = 0


class IoUTracker:
    """Жадное сопоставление по IoU внутри одного класса."""

    def __init__(self, iou_min: float = 0.2, max_missed: int = 4):
        self.iou_min = iou_min
        self.max_missed = max_missed
        self._tracks: list[_State] = []
        self._next_id = 1

    def update(self, detections: list[RawDetection]) -> list[TrackedDetection]:
        pairs = []
        for ti, tr in enumerate(self._tracks):
            for di, det in enumerate(detections):
                if det.class_name != tr.class_name:
                    continue
                score = similarity(tr.bbox, det.bbox)
                if score >= self.iou_min:
                    pairs.append((score, ti, di))
        pairs.sort(reverse=True)

        used_t: set[int] = set()
        assigned: dict[int, int] = {}  # индекс детекции → индекс трека
        for _score, ti, di in pairs:
            if ti in used_t or di in assigned:
                continue
            used_t.add(ti)
            assigned[di] = ti

        result: list[TrackedDetection] = []
        for di, det in enumerate(detections):
            if di in assigned:
                tr = self._tracks[assigned[di]]
                tr.bbox = det.bbox
                tr.missed = 0
            else:
                tr = _State(self._next_id, det.class_name, det.bbox)
                self._next_id += 1
                self._tracks.append(tr)
            result.append(TrackedDetection(tr.track_id, det.class_name, det.confidence, det.bbox))

        seen = {r.track_id for r in result}
        for tr in self._tracks:
            if tr.track_id not in seen:
                tr.missed += 1
        self._tracks = [t for t in self._tracks if t.missed <= self.max_missed]
        return result
