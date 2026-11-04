import numpy as np
import pytest

from ml.classes import is_defect, ru_name
from ml.config import Thresholds
from ml.preprocess import FrameInfo
from ml.scoring import (
    PRIORITY_HIGH,
    PRIORITY_INSUFFICIENT,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    TrackAggregator,
    TrackedDetection,
    compute_priority,
)

TH = Thresholds()  # min_confidence 0.35, high 0.75, medium 0.5, duration_ref 2.0


def test_low_confidence_is_insufficient_data():
    assert compute_priority("insulator_crack", 0.34, 5.0, TH) == PRIORITY_INSUFFICIENT


def test_plain_equipment_is_low_priority():
    assert compute_priority("tower", 0.99, 10.0, TH) == PRIORITY_LOW
    assert compute_priority("insulator", 0.35, 1.0, TH) == PRIORITY_LOW


@pytest.mark.parametrize(
    "conf,duration,expected",
    [
        (0.9, 3.0, PRIORITY_HIGH),  # 0.63 + 0.30 = 0.93
        (0.7, 2.0, PRIORITY_HIGH),  # 0.49 + 0.30 = 0.79
        (0.5, 2.0, PRIORITY_MEDIUM),  # 0.35 + 0.30 = 0.65
        (0.6, 0.5, PRIORITY_LOW),  # 0.42 + 0.075 = 0.495
        (0.4, 0.5, PRIORITY_LOW),  # 0.28 + 0.075 = 0.355
    ],
)
def test_defect_priority(conf, duration, expected):
    assert compute_priority("porcelain_insulator_crack", conf, duration, TH) == expected


def test_threshold_boundaries_just_below_and_above():
    # при длительности ≥ ref score = 0.7·conf + 0.3
    th = Thresholds(min_confidence=0.0, duration_ref_sec=1.0, high=0.9, medium=0.65)
    assert compute_priority("crack", 0.86, 1.0, th) == PRIORITY_HIGH  # 0.902
    assert compute_priority("crack", 0.84, 1.0, th) == PRIORITY_MEDIUM  # 0.888
    assert compute_priority("crack", 0.51, 1.0, th) == PRIORITY_MEDIUM  # 0.657
    assert compute_priority("crack", 0.49, 1.0, th) == PRIORITY_LOW  # 0.643


def test_confidence_exactly_at_minimum_is_not_insufficient():
    assert compute_priority("tower", 0.35, 1.0, TH) == PRIORITY_LOW


def test_defect_detection_by_keywords():
    assert is_defect("Porcelain post insulator crack")
    assert is_defect("bird nest on line")
    assert not is_defect("insulator")
    assert not is_defect("tower")


def test_dataset_codes_are_defects_with_russian_names():
    for code in ("blq_jyjc", "czjyz_ps", "dx_dg", "nw", "yw", "yxdk"):
        assert is_defect(code)
        assert not ru_name(code).startswith("Дефект")
    assert ru_name("czjyz_ps") == "Опорный изолятор: повреждение"
    assert ru_name("nw") == "Гнездо птицы на линии"


def test_dataset_defect_gets_priority_by_confidence():
    assert compute_priority("czjyz_ps", 0.95, 10.0, TH) == PRIORITY_HIGH


def test_ru_names():
    assert ru_name("tower") == "Опора"
    assert ru_name("insulator_crack").startswith("Дефект")


def _frame(i, sharp=200.0):
    return FrameInfo(index=i * 5, time_sec=i * 0.5, sharpness=sharp, brightness=120.0, image=np.full((8, 8, 3), i, np.uint8))


def test_track_detections_merge_into_one_finding():
    agg = TrackAggregator(step_sec=0.5, sharpness_ref=60.0, thresholds=TH)
    bbox = (0.1, 0.2, 0.3, 0.4)
    for i, conf in enumerate([0.5, 0.9, 0.6, 0.7]):
        agg.update(_frame(i), [TrackedDetection(7, "insulator", conf, bbox)])
    findings = agg.to_findings()
    assert len(findings) == 1
    f = findings[0]
    assert f.type == "insulator" and f.track_id == 7
    assert f.confidence == 0.9  # максимум
    assert f.timecode_sec == pytest.approx((0.0 + 1.5) / 2)  # середина интервала
    assert f.bbox == bbox


def test_best_frame_prefers_sharp_over_blurry_with_higher_conf():
    agg = TrackAggregator(0.5, 60.0, TH)
    bbox = (0, 0, 1, 1)
    agg.update(_frame(0, sharp=200.0), [TrackedDetection(1, "tower", 0.80, bbox)])
    agg.update(_frame(1, sharp=6.0), [TrackedDetection(1, "tower", 0.95, bbox)])  # 0.95 * 0.1
    f = agg.to_findings()[0]
    assert int(f.key_image[0, 0, 0]) == 0  # ключевой — первый, резкий кадр


def test_two_tracks_give_two_findings():
    agg = TrackAggregator(0.5, 60.0, TH)
    agg.update(_frame(0), [TrackedDetection(1, "tower", 0.9, (0, 0, 0.1, 0.1)), TrackedDetection(2, "insulator", 0.8, (0.5, 0.5, 0.1, 0.1))])
    assert {f.track_id for f in agg.to_findings()} == {1, 2}


def test_repeated_scoring_is_deterministic():
    def run():
        agg = TrackAggregator(0.5, 60.0, TH)
        for i in range(6):
            agg.update(_frame(i), [TrackedDetection(1, "insulator_crack", 0.8, (0, 0, 0.2, 0.2))])
        return [(f.priority, f.confidence, f.timecode_sec) for f in agg.to_findings()]

    assert run() == run()
