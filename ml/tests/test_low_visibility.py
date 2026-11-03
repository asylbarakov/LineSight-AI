import numpy as np

from ml.low_visibility import LowVisibilityDetector, frame_severity
from ml.preprocess import FrameInfo

IMG = np.zeros((4, 4, 3), np.uint8)
STEP = 0.5


def _frames(pattern: str):
    """'g' — хороший кадр, 'b' — нерезкий, 'd' — тёмный; один символ = один шаг 0.5 с."""
    for i, ch in enumerate(pattern):
        sharp = 10.0 if ch == "b" else 200.0
        bright = 10.0 if ch == "d" else 120.0
        yield FrameInfo(index=i * 5, time_sec=i * STEP, sharpness=sharp, brightness=bright, image=IMG.copy())


def _run(pattern: str, min_sec=2.0):
    det = LowVisibilityDetector(sharpness_min=60, brightness_min=50, min_sec=min_sec, step_sec=STEP)
    for f in _frames(pattern):
        det.update(f)
    return det.finish()


def test_good_video_has_no_intervals():
    assert _run("g" * 20) == []


def test_bad_run_of_two_seconds_is_found():
    iv = _run("gggbbbbggg")  # 4 плохих кадра = 2.0 с
    assert len(iv) == 1
    assert iv[0].start_sec == 1.5
    assert iv[0].duration_sec == 2.0
    assert iv[0].kind == "blur"


def test_short_bad_run_is_ignored():
    assert _run("gggbbbggg") == []  # 3 кадра = 1.5 с < 2 с


def test_good_frame_splits_intervals():
    iv = _run("bbbbgbbbb")
    assert len(iv) == 2


def test_dark_kind_and_confidence_range():
    iv = _run("ggddddddgg")
    assert len(iv) == 1 and iv[0].kind == "dark"
    assert 0.5 <= iv[0].confidence <= 1.0


def test_run_reaching_end_of_video_is_closed():
    iv = _run("gggbbbbb")
    assert len(iv) == 1 and iv[0].end_sec == 4.0


def test_key_frame_is_the_worst_frame():
    det = LowVisibilityDetector(60, 50, 2.0, STEP)
    sharp_values = [50, 20, 5, 30, 40]
    for i, s in enumerate(sharp_values):
        det.update(FrameInfo(i * 5, i * STEP, float(s), 120.0, np.full((2, 2, 3), i, np.uint8)))
    iv = det.finish()
    assert iv[0].key_index == 10  # i=2, sharpness 5


def test_severity_is_bounded():
    assert frame_severity(200, 120, 60, 50) == 0
    assert frame_severity(0, 0, 60, 50) == 1
    assert 0 < frame_severity(30, 120, 60, 50) < 1
