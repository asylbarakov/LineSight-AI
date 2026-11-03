"""Прогон детектора на видео без сервера (задачи 42, 46). `python -m ml.check_detector <weights.pt> <video.mp4>`.

Печатает найденные объекты/дефекты с таймкодами и скорость. Ключевые кадры — в `data/check/frames/`.
"""

from __future__ import annotations

import sys

from .config import PipelineConfig
from .detectors import YoloDetector
from .pipeline import analyze_video


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    weights, video = sys.argv[1], sys.argv[2]
    cfg = PipelineConfig()
    res = analyze_video(video, "data/check", cfg, detector=YoloDetector(weights, cfg.detect_conf))
    print(f"Длительность {res.duration_sec:.1f} с, кадров {res.frames_processed}, {res.fps:.1f} кадр/с")
    print("Этапы, с:", res.stage_times)
    for f in res.findings:
        print(f"{f.timecode_sec:7.1f} с  {f.type:28s} {f.priority:18s} conf={f.confidence:.2f} трек={f.track_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
