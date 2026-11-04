"""Проверка модели на папке изображений с разметкой «есть дефект / нет дефекта» (задача 42, запасной путь).

    python -m ml.check_images data/weights/best.pt data/eval/real_images [--conf 0.25]

В папке: изображения и `labels.json` вида {"img01.jpg": {"label": "defect|clean|uncertain"}}.
Метрика на уровне изображения: для `defect` попадание — найден хотя бы один объект с уверенностью ≥ conf;
для `clean` ложное срабатывание — найден хотя бы один объект. `uncertain` в метрику не входит.
Не проверяет, что рамка стоит на самом дефекте: это нужно смотреть глазами по `annotated/`.
Результат: `<папка>/result.md` и размеченные картинки в `<папка>/annotated/`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

# predict(path, conf) -> [(имя класса, уверенность, (x1, y1, x2, y2) в долях)]
Predict = Callable[[Path, float], list[tuple[str, float, tuple[float, float, float, float]]]]


def evaluate_images(folder: Path, predict: Predict, conf: float) -> dict:
    labels = json.loads((folder / "labels.json").read_text(encoding="utf-8"))
    rows = []
    for name, meta in labels.items():
        if name.startswith("_"):
            continue
        dets = [d for d in predict(folder / name, conf) if d[1] >= conf]
        rows.append({"image": name, "label": meta["label"], "note": meta.get("note", ""), "detections": dets})
    defect = [r for r in rows if r["label"] == "defect"]
    clean = [r for r in rows if r["label"] == "clean"]
    hits = sum(1 for r in defect if r["detections"])
    fps = sum(1 for r in clean if r["detections"])
    return {
        "rows": rows,
        "defect_images": len(defect),
        "defect_hits": hits,
        "recall": hits / len(defect) if defect else None,
        "clean_images": len(clean),
        "clean_false_positives": fps,
    }


def format_report(res: dict, conf: float) -> str:
    lines = [
        "# Проверка модели на изображениях",
        "",
        f"Порог уверенности: {conf}. Метрика на уровне изображения.",
        "",
        "| Изображение | Разметка | Найдено | Комментарий |",
        "| --- | --- | --- | --- |",
    ]
    for r in res["rows"]:
        found = ", ".join(f"{c} {p:.2f}" for c, p, _ in sorted(r["detections"], key=lambda d: -d[1])) or "—"
        lines.append(f"| {r['image']} | {r['label']} | {found} | {r['note']} |")
    rec = "н/д" if res["recall"] is None else f"{res['recall']:.0%}"
    lines += [
        "",
        f"- Изображения с дефектом: найдено хоть что-то на {res['defect_hits']} из {res['defect_images']} (доля {rec}).",
        f"- Изображения без дефекта: ложных срабатываний {res['clean_false_positives']} из {res['clean_images']}.",
    ]
    return "\n".join(lines) + "\n"


def yolo_predict(weights: str) -> Predict:
    from ultralytics import YOLO  # type: ignore

    model = YOLO(weights)

    def predict(path: Path, conf: float):
        r = model.predict(str(path), conf=conf, verbose=False)[0]
        out = []
        for (x1, y1, x2, y2), c, k in zip(r.boxes.xyxyn.cpu().tolist(), r.boxes.conf.cpu().tolist(), r.boxes.cls.int().cpu().tolist()):
            out.append((str(r.names[int(k)]), float(c), (x1, y1, x2, y2)))
        return out

    return predict


def draw(folder: Path, res: dict) -> None:
    import cv2

    out = folder / "annotated"
    out.mkdir(exist_ok=True)
    for r in res["rows"]:
        img = cv2.imread(str(folder / r["image"]))
        if img is None:
            continue
        h, w = img.shape[:2]
        for name, c, (x1, y1, x2, y2) in r["detections"]:
            p1, p2 = (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h))
            cv2.rectangle(img, p1, p2, (0, 0, 255), max(2, w // 400))
            cv2.putText(img, f"{name} {c:.2f}", (p1[0], max(20, p1[1] - 8)), cv2.FONT_HERSHEY_SIMPLEX, max(0.8, w / 1800), (0, 0, 255), 2)
        cv2.imwrite(str(out / r["image"]), img)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("weights")
    ap.add_argument("folder")
    ap.add_argument("--conf", type=float, default=0.25)
    a = ap.parse_args()
    folder = Path(a.folder)
    res = evaluate_images(folder, yolo_predict(a.weights), a.conf)
    report = format_report(res, a.conf)
    (folder / "result.md").write_text(report, encoding="utf-8")
    draw(folder, res)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
