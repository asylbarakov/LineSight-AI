"""Подготовка датасета в формат YOLO (задача 55).

Читает папку или ZIP с изображениями и разметкой в одном из форматов (определяется сам):
  * Pascal VOC (`.xml` рядом с изображением или в соседней папке);
  * COCO (`.json` с ключами `images`/`annotations`/`categories`);
  * YOLO (`.txt`, имена классов — из `classes.txt`, `obj.names` или `data.yaml`).
Полигоны (маски подстанции) превращаются в охватывающие рамки.

Пример для «transmission line object detection.zip» (530 МБ) из sxiong/Power-equipment-image-dataset:
    python -m ml.prepare_dataset --src "transmission line object detection.zip" --out data/datasets/lines_v0

На выходе: `images/{train,val}`, `labels/{train,val}`, `data.yaml`, `classes.json` (статистика по классам).
Разделение train/val 80/20 по изображениям с фиксированным seed — повторный запуск даёт тот же результат.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp"}


@dataclass
class Sample:
    image: Path
    # (имя класса, x_center, y_center, w, h) в долях 0–1
    boxes: list[tuple[str, float, float, float, float]] = field(default_factory=list)


def _clip(v: float) -> float:
    return min(1.0, max(0.0, v))


def xyxy_to_yolo(x1: float, y1: float, x2: float, y2: float, w: float, h: float):
    """Рамка в пикселях → (xc, yc, bw, bh) в долях. None, если рамка вырожденная."""
    x1, x2 = sorted((_clip(x1 / w), _clip(x2 / w)))
    y1, y2 = sorted((_clip(y1 / h), _clip(y2 / h)))
    bw, bh = x2 - x1, y2 - y1
    if bw <= 0 or bh <= 0:
        return None
    return (x1 + bw / 2, y1 + bh / 2, bw, bh)


def polygon_to_yolo(points: list[float], normalized: bool, w: float = 1, h: float = 1):
    xs, ys = points[0::2], points[1::2]
    if not xs:
        return None
    if normalized:
        x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
        return xyxy_to_yolo(x1, y1, x2, y2, 1, 1)
    return xyxy_to_yolo(min(xs), min(ys), max(xs), max(ys), w, h)


# ---------- чтение форматов ----------

def read_voc(xml_path: Path, image_size_fallback: tuple[int, int] | None = None):
    root = ET.parse(xml_path).getroot()
    size = root.find("size")
    w = float(size.findtext("width", "0")) if size is not None else 0
    h = float(size.findtext("height", "0")) if size is not None else 0
    if (not w or not h) and image_size_fallback:
        w, h = image_size_fallback
    if not w or not h:
        return None, []
    boxes = []
    for obj in root.iter("object"):
        name = (obj.findtext("name") or "").strip()
        bnd = obj.find("bndbox")
        if not name or bnd is None:
            continue
        b = xyxy_to_yolo(
            float(bnd.findtext("xmin", "0")), float(bnd.findtext("ymin", "0")),
            float(bnd.findtext("xmax", "0")), float(bnd.findtext("ymax", "0")), w, h,
        )
        if b:
            boxes.append((name, *b))
    return (root.findtext("filename") or "").strip(), boxes


def read_coco(json_path: Path) -> dict[str, list[tuple[str, float, float, float, float]]]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    cats = {c["id"]: c["name"] for c in data.get("categories", [])}
    imgs = {i["id"]: i for i in data.get("images", [])}
    out: dict[str, list] = {}
    for a in data.get("annotations", []):
        img = imgs.get(a.get("image_id"))
        name = cats.get(a.get("category_id"))
        if img is None or name is None or not img.get("width") or not img.get("height"):
            continue
        bbox = a.get("bbox")
        if bbox and len(bbox) == 4:
            x, y, bw, bh = bbox
            b = xyxy_to_yolo(x, y, x + bw, y + bh, img["width"], img["height"])
        else:
            seg = a.get("segmentation")
            if not seg or not isinstance(seg, list) or not isinstance(seg[0], list):
                continue
            b = polygon_to_yolo(seg[0], False, img["width"], img["height"])
        if b:
            out.setdefault(Path(img["file_name"]).name, []).append((name, *b))
    for i in imgs.values():  # изображения без аннотаций тоже нужны (фоновые кадры)
        out.setdefault(Path(i["file_name"]).name, [])
    return out


def read_yolo_names(root: Path) -> list[str] | None:
    for fname in ("classes.txt", "obj.names", "names.txt"):
        for p in root.rglob(fname):
            return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for p in root.rglob("data.yaml"):
        text = p.read_text(encoding="utf-8")
        m = re.search(r"names:\s*\[(.*?)\]", text, re.S)
        if m:
            return [s.strip().strip("'\"") for s in m.group(1).split(",") if s.strip()]
        m = re.search(r"names:\s*\n((?:\s+\d+:\s*.+\n?)+)", text)
        if m:
            return [ln.split(":", 1)[1].strip().strip("'\"") for ln in m.group(1).splitlines() if ":" in ln]
    return None


def read_yolo_txt(txt_path: Path, names: list[str]):
    boxes = []
    for ln in txt_path.read_text(encoding="utf-8").splitlines():
        parts = ln.split()
        if len(parts) < 5:
            continue
        cid = int(float(parts[0]))
        vals = [float(v) for v in parts[1:]]
        name = names[cid] if cid < len(names) else f"class_{cid}"
        if len(vals) == 4:
            xc, yc, bw, bh = vals
            b = (xc, yc, bw, bh) if bw > 0 and bh > 0 else None
        else:  # полигон
            b = polygon_to_yolo(vals, True)
        if b:
            boxes.append((name, *b))
    return boxes


# ---------- сборка ----------

def _image_size(path: Path) -> tuple[int, int] | None:
    import cv2

    img = cv2.imread(str(path))
    return None if img is None else (img.shape[1], img.shape[0])


def collect(root: Path) -> list[Sample]:
    images = {p.stem: p for p in sorted(root.rglob("*")) if p.suffix.lower() in IMAGE_EXT}
    by_name = {p.name: p for p in images.values()}
    samples: dict[Path, Sample] = {}

    coco_files = []
    for jp in root.rglob("*.json"):
        try:
            head = json.loads(jp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(head, dict) and "images" in head and "annotations" in head:
            coco_files.append(jp)
    for jp in coco_files:
        for fname, boxes in read_coco(jp).items():
            img = by_name.get(fname)
            if img is not None:
                samples.setdefault(img, Sample(img)).boxes.extend(boxes)

    for xp in sorted(root.rglob("*.xml")):
        img = images.get(xp.stem)
        if img is None:
            continue
        _, boxes = read_voc(xp, _image_size(img))
        samples.setdefault(img, Sample(img)).boxes.extend(boxes)

    names = read_yolo_names(root)
    if names is not None:
        for tp in sorted(root.rglob("*.txt")):
            img = images.get(tp.stem)
            if img is None or tp.name in {"classes.txt", "obj.names", "names.txt"}:
                continue
            samples.setdefault(img, Sample(img)).boxes.extend(read_yolo_txt(tp, names))
    return list(samples.values())


def build(
    src: Path,
    out: Path,
    val_ratio: float = 0.2,
    seed: int = 0,
    min_instances: int = 1,
    keep_empty: bool = False,
    link: bool = False,
) -> dict:
    """Конвертирует датасет. Возвращает сводку (число изображений, классы, статистика)."""
    tmp = None
    if src.is_file() and src.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="ds_"))
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        root = tmp
    else:
        root = src
    try:
        samples = collect(root)
        if not keep_empty:
            samples = [s for s in samples if s.boxes]
        if not samples:
            raise SystemExit("Не найдено ни одного изображения с разметкой: проверьте формат и путь")

        counts = Counter(b[0] for s in samples for b in s.boxes)
        names = sorted(n for n, c in counts.items() if c >= min_instances)
        index = {n: i for i, n in enumerate(names)}
        samples = [Sample(s.image, [b for b in s.boxes if b[0] in index]) for s in samples]
        if not keep_empty:
            samples = [s for s in samples if s.boxes]

        rng = random.Random(seed)
        order = sorted(samples, key=lambda s: str(s.image))
        rng.shuffle(order)
        n_val = max(1, int(len(order) * val_ratio)) if len(order) > 1 else 0
        split = {"val": order[:n_val], "train": order[n_val:]}

        if out.exists():
            shutil.rmtree(out)
        stats = {"train": Counter(), "val": Counter()}
        used_names: set[str] = set()
        for part, items in split.items():
            (out / "images" / part).mkdir(parents=True)
            (out / "labels" / part).mkdir(parents=True)
            for s in items:
                stem, k = s.image.stem, 0
                while f"{stem}{'' if k == 0 else f'_{k}'}" in used_names:
                    k += 1
                stem = f"{stem}{'' if k == 0 else f'_{k}'}"
                used_names.add(stem)
                dst = out / "images" / part / f"{stem}{s.image.suffix.lower()}"
                if link and tmp is None:
                    dst.symlink_to(s.image.resolve())
                else:
                    shutil.copy2(s.image, dst)
                lines = []
                for name, xc, yc, bw, bh in s.boxes:
                    lines.append(f"{index[name]} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
                    stats[part][name] += 1
                (out / "labels" / part / f"{stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

        yaml = [f"path: {out.resolve()}", "train: images/train", "val: images/val", "names:"]
        yaml += [f"  {i}: {n}" for i, n in enumerate(names)]
        (out / "data.yaml").write_text("\n".join(yaml) + "\n", encoding="utf-8")
        summary = {
            "images": {p: len(v) for p, v in split.items()},
            "classes": names,
            "instances": {p: dict(stats[p]) for p in stats},
            "dropped_classes": sorted(n for n, c in counts.items() if c < min_instances),
        }
        (out / "classes.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="папка или .zip с датасетом")
    ap.add_argument("--out", default="data/datasets/lines_v0")
    ap.add_argument("--val-ratio", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-instances", type=int, default=20, help="классы реже этого числа отбрасываются")
    ap.add_argument("--keep-empty", action="store_true", help="оставить изображения без объектов (фон)")
    ap.add_argument("--link", action="store_true", help="симлинки вместо копирования (только для папки)")
    a = ap.parse_args()
    s = build(Path(a.src), Path(a.out), a.val_ratio, a.seed, a.min_instances, a.keep_empty, a.link)
    print(f"Изображений: train {s['images']['train']}, val {s['images']['val']}; классов: {len(s['classes'])}")
    if s["dropped_classes"]:
        print("Отброшены редкие классы:", ", ".join(s["dropped_classes"]))
    print(f"data.yaml: {Path(a.out) / 'data.yaml'}")


if __name__ == "__main__":
    main()
