from pathlib import Path

from ml import evaluate as ev
from ml import regression as rg
from ml.make_synthetic import make_video


def test_low_visibility_matching_within_tolerance():
    exp = [{"type": "low_visibility", "start_sec": 9.0, "end_sec": 16.0}]
    ok = ev.compare(exp, [{"type": "low_visibility", "timecode_sec": 10.5}])["low_visibility"]
    assert (ok.tp, ok.fp, ok.fn) == (1, 0, 0)
    far = ev.compare(exp, [{"type": "low_visibility", "timecode_sec": 14.0}])["low_visibility"]
    assert (far.tp, far.fp, far.fn) == (0, 1, 1)


def test_each_found_matches_once():
    exp = [{"type": "tower", "start_sec": 0, "end_sec": 10}, {"type": "tower", "start_sec": 0, "end_sec": 10}]
    found = [{"type": "tower", "timecode_sec": 5}]
    s = ev.compare(exp, found)["objects"]
    assert (s.tp, s.fp, s.fn) == (1, 0, 1) and s.recall == 0.5 and s.precision == 1.0


def test_wrong_class_is_not_matched():
    s = ev.compare([{"type": "tower", "start_sec": 0, "end_sec": 5}], [{"type": "insulator", "timecode_sec": 2}])["objects"]
    assert (s.tp, s.fp, s.fn) == (0, 1, 1)


def test_empty_expected_gives_full_scores():
    s = ev.compare([], [])["low_visibility"]
    assert s.precision == 1.0 and s.recall == 1.0


def test_build_ground_truth_from_synthetic(tmp_path):
    make_video(tmp_path / "v.mp4", duration=8.0, fps=10, blur=[(2.0, 6.0)], seed=1)
    gt = ev.build_ground_truth(tmp_path)
    exp = gt["videos"]["v.mp4"]["expected"]
    assert {"type": "low_visibility", "start_sec": 2.0, "end_sec": 6.0} in exp
    assert any(e["type"] == "tower" for e in exp)


def test_regression_check_flags_drops_and_threshold():
    cur = {"a.mp4": {"low_visibility": 0.5, "objects": 0.9}}
    assert rg.check(cur, None)  # recall ниже 0.8 без базовой линии
    base = {"a.mp4": {"low_visibility": 0.55, "objects": 0.95}}
    assert rg.check(cur, base) == []  # просадка в пределах допуска 0.05 (0.5 ≥ 0.55-0.05; 0.9 ≥ 0.95-0.05)
    assert rg.check({"a.mp4": {"low_visibility": 0.4, "objects": 0.9}}, base)


def test_end_to_end_on_synthetic_detects_blur(tmp_path):
    make_video(tmp_path / "b.mp4", duration=16.0, fps=10, blur=[(5.0, 11.0)], seed=5)
    gt = ev.build_ground_truth(tmp_path)
    found = ev.run_local(tmp_path, gt, "synthetic", tmp_path / "work")
    scores = ev.compare(gt["videos"]["b.mp4"]["expected"], found["b.mp4"])
    assert scores["low_visibility"].recall == 1.0 and scores["low_visibility"].precision == 1.0
