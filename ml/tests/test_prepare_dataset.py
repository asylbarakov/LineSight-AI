import json
import zipfile

import cv2
import numpy as np
import pytest

from ml import prepare_dataset as pd


def _img(path, w=200, h=100):
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.full((h, w, 3), 128, dtype=np.uint8))


def test_xyxy_to_yolo_and_degenerate():
    assert pd.xyxy_to_yolo(0, 0, 100, 50, 200, 100) == pytest.approx((0.25, 0.25, 0.5, 0.5))
    assert pd.xyxy_to_yolo(10, 10, 10, 50, 200, 100) is None
    assert pd.xyxy_to_yolo(-50, -50, 400, 300, 200, 100) == pytest.approx((0.5, 0.5, 1.0, 1.0))  # обрезка


def test_polygon_to_bbox():
    b = pd.polygon_to_yolo([0.2, 0.2, 0.6, 0.2, 0.6, 0.8], True)
    assert b == pytest.approx((0.4, 0.5, 0.4, 0.6))


def test_voc_dataset(tmp_path):
    src = tmp_path / "voc"
    for i in range(10):
        _img(src / f"a{i}.jpg")
        (src / f"a{i}.xml").write_text(
            f"<annotation><filename>a{i}.jpg</filename><size><width>200</width><height>100</height></size>"
            "<object><name>insulator</name><bndbox><xmin>20</xmin><ymin>10</ymin><xmax>120</xmax><ymax>60</ymax></bndbox></object>"
            "<object><name>tower</name><bndbox><xmin>0</xmin><ymin>0</ymin><xmax>40</xmax><ymax>100</ymax></bndbox></object>"
            "</annotation>", encoding="utf-8")
    s = pd.build(src, tmp_path / "out", val_ratio=0.2, seed=1, min_instances=1)
    assert s["classes"] == ["insulator", "tower"]
    assert s["images"] == {"val": 2, "train": 8}
    out = tmp_path / "out"
    assert "0: insulator" in (out / "data.yaml").read_text()
    label = next((out / "labels" / "train").glob("*.txt")).read_text().split("\n")[0].split()
    assert label[0] == "0" and float(label[1]) == pytest.approx(0.35)


def test_coco_dataset_from_zip_and_rare_class_dropped(tmp_path):
    root = tmp_path / "coco"
    anns, images = [], []
    for i in range(6):
        _img(root / f"c{i}.jpg")
        images.append({"id": i, "file_name": f"c{i}.jpg", "width": 200, "height": 100})
        anns.append({"image_id": i, "category_id": 1, "bbox": [10, 10, 50, 40]})
    anns.append({"image_id": 0, "category_id": 2, "bbox": [0, 0, 20, 20]})  # редкий класс
    (root / "ann.json").write_text(json.dumps({
        "images": images, "annotations": anns,
        "categories": [{"id": 1, "name": "crack"}, {"id": 2, "name": "rare"}]}), encoding="utf-8")
    zp = tmp_path / "ds.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for p in root.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(root))
    s = pd.build(zp, tmp_path / "out", min_instances=3)
    assert s["classes"] == ["crack"] and s["dropped_classes"] == ["rare"]


def test_yolo_dataset_with_polygon(tmp_path):
    src = tmp_path / "y"
    (src).mkdir()
    (src / "classes.txt").write_text("tower\ninsulator\n", encoding="utf-8")
    for i in range(4):
        _img(src / f"y{i}.jpg")
        (src / f"y{i}.txt").write_text("0 0.5 0.5 0.2 0.4\n1 0.1 0.1 0.5 0.1 0.5 0.3 0.1 0.3\n", encoding="utf-8")
    s = pd.build(src, tmp_path / "out", min_instances=1)
    assert s["classes"] == ["insulator", "tower"]
    assert sum(s["instances"]["train"].values()) + sum(s["instances"]["val"].values()) == 8


def test_split_is_reproducible(tmp_path):
    src = tmp_path / "v"
    for i in range(20):
        _img(src / f"p{i}.jpg")
        (src / f"p{i}.xml").write_text(
            "<annotation><size><width>200</width><height>100</height></size>"
            "<object><name>a</name><bndbox><xmin>1</xmin><ymin>1</ymin><xmax>50</xmax><ymax>50</ymax></bndbox></object></annotation>",
            encoding="utf-8")
    pd.build(src, tmp_path / "o1", seed=3, min_instances=1)
    pd.build(src, tmp_path / "o2", seed=3, min_instances=1)
    v1 = sorted(p.name for p in (tmp_path / "o1" / "images" / "val").iterdir())
    v2 = sorted(p.name for p in (tmp_path / "o2" / "images" / "val").iterdir())
    assert v1 == v2 and len(v1) == 4


def test_no_annotations_exits(tmp_path):
    _img(tmp_path / "s" / "x.jpg")
    with pytest.raises(SystemExit):
        pd.build(tmp_path / "s", tmp_path / "out")
