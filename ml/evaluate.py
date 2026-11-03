"""Эталон и сравнение «найдено против ожидаемого» (задача 60).

`ground_truth.json` собирается из JSON-эталонов синтетики (`make_synthetic`) и ручной разметки.
Допуск по времени — ±2 секунды. Выводит precision/recall по каждому видео.

    python -m ml.evaluate build data/demo            # собрать data/demo/ground_truth.json
    python -m ml.evaluate run data/demo [--detector none|synthetic|yolo]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

TOLERANCE_SEC = 2.0


@dataclass
class Score:
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 1.0


def build_ground_truth(demo_dir: Path) -> dict:
    """Собирает эталон по всем `*.json` с ключом `low_visibility` в папке."""
    videos: dict[str, dict] = {}
    for p in sorted(demo_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict) or "low_visibility" not in data:
            continue
        videos[data.get("video", p.with_suffix(".mp4").name)] = {
            "duration_sec": data.get("duration_sec"),
            "expected": [
                {"type": "low_visibility", "start_sec": x["start_sec"], "end_sec": x["end_sec"]}
                for x in data["low_visibility"]
            ]
            + [
                {"type": o["class"], "start_sec": o["first_sec"], "end_sec": o["last_sec"]}
                for o in data.get("objects", [])
            ],
        }
    return {"tolerance_sec": TOLERANCE_SEC, "videos": videos}


def _match(expected: list[dict], found: list[dict], tol: float, point) -> Score:
    """Жадное сопоставление по типу и времени: каждое ожидаемое и найденное — не более одного раза."""
    used: set[int] = set()
    tp = 0
    for e in expected:
        for i, f in enumerate(found):
            if i in used or f["type"] != e["type"]:
                continue
            if point(e, f, tol):
                used.add(i)
                tp += 1
                break
    return Score(tp=tp, fp=len(found) - len(used), fn=len(expected) - tp)


def _lv_point(e: dict, f: dict, tol: float) -> bool:
    # таймкод находки «недостаточная видимость» — начало интервала
    return abs(f["timecode_sec"] - e["start_sec"]) <= tol


def _obj_point(e: dict, f: dict, tol: float) -> bool:
    # таймкод находки по объекту — середина времени, пока он в кадре
    return e["start_sec"] - tol <= f["timecode_sec"] <= e["end_sec"] + tol


def compare(expected: list[dict], found: list[dict], tol: float = TOLERANCE_SEC) -> dict[str, Score]:
    """Возвращает оценки отдельно для `low_visibility` и для объектов."""
    exp_lv = [e for e in expected if e["type"] == "low_visibility"]
    exp_obj = [e for e in expected if e["type"] != "low_visibility"]
    f_lv = [f for f in found if f["type"] == "low_visibility"]
    f_obj = [f for f in found if f["type"] != "low_visibility"]
    return {
        "low_visibility": _match(exp_lv, f_lv, tol, _lv_point),
        "objects": _match(exp_obj, f_obj, tol, _obj_point),
    }


def format_table(rows: dict[str, dict[str, Score]]) -> str:
    out = ["| Видео | Тип | TP | FP | FN | Precision | Recall |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for video, scores in rows.items():
        for kind, s in scores.items():
            out.append(f"| {video} | {kind} | {s.tp} | {s.fp} | {s.fn} | {s.precision:.2f} | {s.recall:.2f} |")
    return "\n".join(out)


def run_local(demo_dir: Path, truth: dict, detector_name: str, work: Path) -> dict[str, list[dict]]:
    """Прогоняет пайплайн на каждом видео из эталона и возвращает находки в виде словарей."""
    from .config import PipelineConfig
    from .detectors import make_detector
    from .pipeline import analyze_video

    cfg = PipelineConfig(detector=detector_name)
    results: dict[str, list[dict]] = {}
    for name in truth["videos"]:
        video = demo_dir / name
        if not video.is_file():
            continue
        res = analyze_video(str(video), str(work / video.stem), cfg, detector=make_detector(cfg))
        results[name] = [
            {"type": f.type, "timecode_sec": f.timecode_sec, "confidence": f.confidence, "priority": f.priority}
            for f in res.findings
        ]
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "run"])
    ap.add_argument("demo_dir")
    ap.add_argument("--detector", default="synthetic")
    a = ap.parse_args()
    demo = Path(a.demo_dir)
    gt_path = demo / "ground_truth.json"
    if a.cmd == "build":
        gt = build_ground_truth(demo)
        gt_path.write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{gt_path}: видео {len(gt['videos'])}")
        return 0
    truth = json.loads(gt_path.read_text(encoding="utf-8"))
    found = run_local(demo, truth, a.detector, Path("data/eval"))
    rows = {v: compare(truth["videos"][v]["expected"], f, truth.get("tolerance_sec", TOLERANCE_SEC)) for v, f in found.items()}
    print(format_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
