import cv2
import numpy as np
import pytest

from ml import preprocess
from ml.errors import E_DECODE, E_VIDEO_INVALID, PipelineError
from ml.preprocess import brightness, iter_frames, probe_video, sharpness


def _write_video(path, n=40, fps=10, size=(320, 240)):
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    rng = np.random.default_rng(0)
    for i in range(n):
        frame = rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)
        cv2.putText(frame, str(i), (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        w.write(frame)
    w.release()


def test_timecodes_match_frame_index(tmp_path):
    p = tmp_path / "v.mp4"
    _write_video(p, n=40, fps=10)
    frames = list(iter_frames(str(p), step_sec=0.5))  # каждые 5 кадров
    assert [f.index for f in frames] == [0, 5, 10, 15, 20, 25, 30, 35]
    for f in frames:
        assert f.time_sec == pytest.approx(f.index / 10)


def test_blurry_frame_scores_lower_than_sharp():
    rng = np.random.default_rng(1)
    sharp_img = rng.integers(0, 255, (360, 640, 3), dtype=np.uint8)
    blurred = cv2.GaussianBlur(sharp_img, (0, 0), 6)
    assert sharpness(blurred) < sharpness(sharp_img)


def test_sharpness_does_not_depend_on_resolution_much():
    rng = np.random.default_rng(2)
    small = rng.integers(0, 255, (360, 640, 3), dtype=np.uint8)
    big = cv2.resize(small, (1920, 1080), interpolation=cv2.INTER_NEAREST)
    # после приведения к ширине 640 значения одного порядка
    assert 0.3 < sharpness(big) / sharpness(small) < 3.0


def test_brightness():
    assert brightness(np.zeros((10, 10, 3), np.uint8)) == 0
    assert brightness(np.full((10, 10, 3), 200, np.uint8)) == pytest.approx(200)


def test_not_a_video_gives_e_video_invalid(tmp_path):
    p = tmp_path / "fake.mp4"
    p.write_text("это не видео")
    with pytest.raises(PipelineError) as e:
        probe_video(str(p))
    assert e.value.code == E_VIDEO_INVALID


def test_missing_file_gives_e_video_invalid(tmp_path):
    with pytest.raises(PipelineError) as e:
        list(iter_frames(str(tmp_path / "нет.mp4"), 0.5))
    assert e.value.code == E_VIDEO_INVALID


def test_unreadable_frames_give_e_decode(tmp_path, monkeypatch):
    """Метаданные корректны, но кадры не читаются → E_DECODE."""
    p = tmp_path / "v.mp4"
    _write_video(p, n=10)

    class BrokenCap:
        def __init__(self, *_a):
            pass

        def isOpened(self):
            return True

        def read(self):
            return False, None

        def grab(self):
            return False

        def release(self):
            pass

    monkeypatch.setattr(preprocess, "probe_video", lambda _p: preprocess.VideoMeta(10.0, 10, 320, 240))
    monkeypatch.setattr(preprocess.cv2, "VideoCapture", BrokenCap)
    with pytest.raises(PipelineError) as e:
        list(iter_frames(str(p), 0.5))
    assert e.value.code == E_DECODE
