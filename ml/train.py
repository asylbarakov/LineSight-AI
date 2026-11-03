"""Обучение и дообучение YOLO (задачи 45 и 50). Запускается в Colab/Kaggle или на локальной GPU.

Первое обучение:
    python -m ml.train --data data/datasets/lines_v0/data.yaml --model yolov8s.pt --epochs 40
Дообучение по разбору ошибок (на лучших весах, 10–20 эпох):
    python -m ml.train --data data/datasets/lines_v1/data.yaml --model data/weights/best.pt --epochs 15 --name finetune

После обучения лучшие веса копируются в `data/weights/best.pt`, метрики — в `data/weights/metrics.json`.
Если файл `best.pt` уже есть, он сохраняется как `best.prev.pt` (чтобы сравнить «до» и «после»).
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="data.yaml в формате YOLO")
    ap.add_argument("--model", default="yolov8s.pt", help="yolov8n.pt / yolov8s.pt или путь к своим весам")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16, help="-1: подобрать автоматически по памяти GPU")
    ap.add_argument("--device", default=None, help="0, cpu; по умолчанию выбирает Ultralytics")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--project", default="data/runs")
    ap.add_argument("--name", default="linesight")
    ap.add_argument("--weights-dir", default="data/weights")
    a = ap.parse_args()

    from ultralytics import YOLO  # импорт здесь: модуль нужен только на машине с обучением

    model = YOLO(a.model)
    model.train(
        data=a.data, epochs=a.epochs, imgsz=a.imgsz, batch=a.batch, device=a.device,
        workers=a.workers, project=a.project, name=a.name, exist_ok=True, patience=15,
    )
    run_dir = Path(model.trainer.save_dir)
    best = run_dir / "weights" / "best.pt"
    if not best.is_file():
        raise SystemExit(f"Не найден файл весов: {best}")

    metrics = YOLO(str(best)).val(data=a.data, imgsz=a.imgsz, device=a.device, verbose=False)
    out_dir = Path(a.weights_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "best.pt"
    if target.is_file():
        shutil.copy2(target, out_dir / "best.prev.pt")
    shutil.copy2(best, target)
    summary = {
        "weights": str(target),
        "data": a.data,
        "epochs": a.epochs,
        "model": a.model,
        "map50": round(float(metrics.box.map50), 4),
        "map50_95": round(float(metrics.box.map), 4),
        "classes": list(metrics.names.values()) if hasattr(metrics, "names") else [],
    }
    (out_dir / "metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
