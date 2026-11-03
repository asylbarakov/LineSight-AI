import json
from pathlib import Path

import pytest

from ml.config import PipelineConfig
from ml.detectors import SyntheticDetector, YoloDetector, make_detector
from ml.errors import E_MODEL, E_VIDEO_INVALID, PipelineError
from ml.make_synthetic import make_video
from ml.pipeline import analyze_video


@pytest.fixture(scope="module")
def blur_video(tmp_path_factory):
    d = tmp_path_factory.mktemp("synth")
    path = d / "blur.mp4"
    truth = make_video(path, duration=16.0, fps=10, blur=[(5.0, 11.0)], seed=5)
    return path, truth


@pytest.fixture(scope="module")
def clean_video(tmp_path_factory):
    d = tmp_path_factory.mktemp("synth_clean")
    path = d / "clean.mp4"
    make_video(path, duration=16.0, fps=10, seed=6)
    return path


def test_ground_truth_file_written(blur_video):
    path, truth = blur_video
    saved = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert saved["low_visibility"] == truth["low_visibility"]
    assert truth["low_visibility"][0]["start_sec"] == 5.0


def test_low_visibility_found_on_blurry_video(blur_video, tmp_path):
    path, _ = blur_video
    res = analyze_video(str(path), str(tmp_path), PipelineConfig(detector="none"))
    lv = [f for f in res.findings if f.type == "low_visibility"]
    assert len(lv) == 1
    assert abs(lv[0].timecode_sec - 5.0) <= 1.0
    assert lv[0].priority == "insufficient_data"
    assert (tmp_path / lv[0].frame_path).is_file()
    assert res.duration_sec == pytest.approx(16.0, abs=0.2)
    assert res.fps > 0 and set(res.stage_times) >= {"decode", "detect", "track", "findings", "total"}


def test_clean_video_has_no_low_visibility(clean_video, tmp_path):
    res = analyze_video(str(clean_video), str(tmp_path), PipelineConfig(detector="none"))
    assert [f for f in res.findings if f.type == "low_visibility"] == []
    assert res.findings == []


def test_one_object_is_one_finding_on_clean_video(clean_video, tmp_path):
    res = analyze_video(str(clean_video), str(tmp_path), PipelineConfig(detector="synthetic"))
    keys = [(f.type, f.track_id) for f in res.findings]
    assert len(keys) == len(set(keys))  # дублей нет
    towers = [f for f in res.findings if f.type == "tower"]
    insulators = [f for f in res.findings if f.type == "insulator"]
    assert 1 <= len(towers) <= 3 and 2 <= len(insulators) <= 6
    for f in res.findings:
        x, y, w, h = f.bbox
        assert 0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1
        assert (tmp_path / f.frame_path).is_file()


def test_rerun_gives_same_result(clean_video, tmp_path):
    cfg = PipelineConfig(detector="synthetic")
    a = analyze_video(str(clean_video), str(tmp_path / "a"), cfg)
    b = analyze_video(str(clean_video), str(tmp_path / "b"), cfg)
    sig = lambda r: [(f.type, f.priority, f.confidence, f.timecode_sec) for f in r.findings]  # noqa: E731
    assert sig(a) == sig(b)


def test_progress_callback_is_called(blur_video, tmp_path):
    path, _ = blur_video
    seen = []
    analyze_video(str(path), str(tmp_path), PipelineConfig(detector="none"), progress=seen.append)
    assert seen and all(0 <= p < 1 for p in seen)


def test_broken_file_gives_e_video_invalid(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_text("not a video")
    with pytest.raises(PipelineError) as e:
        analyze_video(str(bad), str(tmp_path / "out"), PipelineConfig(detector="none"))
    assert e.value.code == E_VIDEO_INVALID


def test_missing_weights_give_e_model(tmp_path):
    cfg = PipelineConfig(detector="yolo", model_path=str(tmp_path / "нет.pt"))
    with pytest.raises(PipelineError) as e:
        make_detector(cfg)
    assert e.value.code == E_MODEL
    with pytest.raises(PipelineError) as e2:
        YoloDetector(str(tmp_path / "нет.pt"))
    assert e2.value.code == E_MODEL


def test_auto_without_weights_falls_back_to_no_detector(tmp_path):
    cfg = PipelineConfig(detector="auto", model_path=str(tmp_path / "нет.pt"))
    assert make_detector(cfg) is None


def test_synthetic_detector_factory():
    assert isinstance(make_detector(PipelineConfig(detector="synthetic")), SyntheticDetector)


def test_unknown_detector_name_gives_e_model():
    with pytest.raises(PipelineError) as e:
        make_detector(PipelineConfig(detector="что-то"))
    assert e.value.code == E_MODEL


def test_demo_videos_script_paths_exist():
    assert Path("ml/make_synthetic.py").is_file()
