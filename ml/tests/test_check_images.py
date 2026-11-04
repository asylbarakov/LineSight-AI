import json

from ml.check_images import evaluate_images, format_report


def _folder(tmp_path):
    labels = {
        "_comment": "x",
        "a.jpg": {"label": "defect"},
        "b.jpg": {"label": "defect"},
        "c.jpg": {"label": "clean"},
        "d.jpg": {"label": "clean"},
        "e.jpg": {"label": "uncertain"},
    }
    (tmp_path / "labels.json").write_text(json.dumps(labels), encoding="utf-8")
    return tmp_path


def test_recall_and_false_positives(tmp_path):
    folder = _folder(tmp_path)
    box = (0.1, 0.1, 0.4, 0.4)
    table = {"a.jpg": [("czjyz_ps", 0.8, box)], "b.jpg": [], "c.jpg": [("nw", 0.6, box)], "d.jpg": [], "e.jpg": [("yw", 0.9, box)]}
    res = evaluate_images(folder, lambda p, conf: table[p.name], 0.25)
    assert res["defect_images"] == 2 and res["defect_hits"] == 1 and res["recall"] == 0.5
    assert res["clean_images"] == 2 and res["clean_false_positives"] == 1
    assert "uncertain" in format_report(res, 0.25)  # спорное попадает в таблицу, но не в метрику


def test_detections_below_conf_are_ignored(tmp_path):
    folder = _folder(tmp_path)
    box = (0, 0, 1, 1)
    res = evaluate_images(folder, lambda p, conf: [("nw", 0.1, box)], 0.25)
    assert res["defect_hits"] == 0 and res["clean_false_positives"] == 0
