"""Тесты PDF-отчёта и русских шаблонов (не требуют БД и FastAPI)."""

from datetime import datetime, timezone

import cv2
import numpy as np

from app import report, texts


def _frame(path, w=640, h=360):
    img = np.full((h, w, 3), 90, dtype=np.uint8)
    cv2.rectangle(img, (200, 100), (320, 240), (200, 200, 200), -1)
    cv2.imwrite(str(path), img)


def test_fmt_timecode():
    assert texts.fmt_timecode(0) == "00:00"
    assert texts.fmt_timecode(73.4) == "01:13"
    assert texts.fmt_timecode(-5) == "00:00"


def test_describe_is_russian_without_english_leftovers():
    s = texts.describe("insulator", "medium", 0.914, 20.5)
    assert s == "Изолятор на отметке 00:20, приоритет средний, уверенность 91%"
    lv = texts.describe("low_visibility", "insufficient_data", 0.8, 12)
    assert "Недостаточная видимость" in lv and "недостаточно данных" in lv


def test_recommendation_for_low_visibility():
    assert texts.recommendation("low_visibility", "insufficient_data") == texts.LOW_VISIBILITY_NOTE
    assert "первую очередь" in texts.recommendation("insulator_crack", "high")


def test_priority_and_status_dictionaries_cover_contract():
    assert set(texts.PRIORITY_RU) == {"high", "medium", "low", "insufficient_data"}
    assert set(texts.STATUS_RU) == {"new", "confirmed", "rejected", "reshoot"}
    assert set(texts.ERROR_RU) == {"E_VIDEO_INVALID", "E_DECODE", "E_MODEL", "E_TIMEOUT"}


def test_draw_bbox_does_not_touch_original_and_draws_rectangle(tmp_path):
    p = tmp_path / "f.jpg"
    _frame(p)
    before = p.read_bytes()
    jpeg = report.draw_bbox_jpeg(p, (0.3, 0.3, 0.2, 0.4))
    assert jpeg is not None and jpeg[:2] == b"\xff\xd8"
    assert p.read_bytes() == before
    out = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    # на рамке (левая граница, x = 0.3 * 640 = 192) должен быть красноватый пиксель
    assert out[200, 192, 2] > 150 and out[200, 192, 0] < 100


def test_draw_bbox_missing_file_returns_none(tmp_path):
    assert report.draw_bbox_jpeg(tmp_path / "nope.jpg", None) is None


def test_build_pdf_with_findings_and_empty(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    _frame(frames / "t1.jpg")
    findings = [
        {"type": "insulator", "priority": "high", "confidence": 0.93, "timecode_sec": 20.5,
         "frame_path": "frames/t1.jpg", "bbox": {"x": 0.3, "y": 0.3, "w": 0.2, "h": 0.4}, "status": "confirmed"},
        {"type": "low_visibility", "priority": "insufficient_data", "confidence": 0.8, "timecode_sec": 5,
         "frame_path": None, "bbox": None, "status": "new"},
    ]
    out = report.build_pdf(
        tmp_path / "r.pdf", title="Облёт участка 1", created_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
        duration_sec=42.5, findings=findings, frames_dir=frames,
    )
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 3000

    empty = report.build_pdf(
        tmp_path / "e.pdf", title="Пусто", created_at=None, duration_sec=None, findings=[], frames_dir=frames,
    )
    assert empty.read_bytes().startswith(b"%PDF")


def test_needs_rebuild_by_decision_time(tmp_path):
    f = tmp_path / "r.pdf"
    assert report._needs_rebuild(f, [])  # файла нет
    f.write_bytes(b"%PDF")
    assert not report._needs_rebuild(f, [None, datetime(2000, 1, 1, tzinfo=timezone.utc)])
    assert report._needs_rebuild(f, [datetime(2100, 1, 1, tzinfo=timezone.utc)])
