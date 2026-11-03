"""PDF-отчёт на русском (задачи 37–38). reportlab + шрифт с кириллицей (DejaVu Sans).

Отчёт кэшируется в `report.pdf` и пересоздаётся, если после его создания изменились решения
инженера или данные инспекции.

НЕ ПРОВЕРЕНО в песочнице разработки (нет SQLAlchemy): логика отрисовки проверяется тестом
`backend/tests/test_report.py`, который не требует БД.
"""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import texts

log = logging.getLogger("linesight.report")

FONT = "LSFont"
FONT_BOLD = "LSFont-Bold"

_FONT_CANDIDATES = (
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
)

_fonts_ready = False


def _register_fonts() -> None:
    global _fonts_ready
    if _fonts_ready:
        return
    override = os.environ.get("REPORT_FONT")
    candidates = list(_FONT_CANDIDATES)
    if override:
        candidates.insert(0, (override, override))
    for regular, bold in candidates:
        if os.path.isfile(regular):
            pdfmetrics.registerFont(TTFont(FONT, regular))
            pdfmetrics.registerFont(TTFont(FONT_BOLD, bold if os.path.isfile(bold) else regular))
            _fonts_ready = True
            return
    raise RuntimeError("Не найден шрифт с кириллицей (установите fonts-dejavu-core или задайте REPORT_FONT)")


PRIORITY_COLORS = {
    "high": colors.HexColor("#c62828"),
    "medium": colors.HexColor("#ef8f00"),
    "low": colors.HexColor("#2e7d32"),
    "insufficient_data": colors.HexColor("#546e7a"),
}


def draw_bbox_jpeg(image_path: Path, bbox: tuple[float, float, float, float] | None, max_width: int = 900) -> bytes | None:
    """Копия кадра с рамкой (bbox в долях 0–1). Оригинал не меняется."""
    img = cv2.imread(str(image_path))
    if img is None:
        return None
    h, w = img.shape[:2]
    if bbox is not None:
        x, y, bw, bh = bbox
        p1 = (int(x * w), int(y * h))
        p2 = (int((x + bw) * w), int((y + bh) * h))
        thickness = max(2, round(min(w, h) / 200))
        cv2.rectangle(img, p1, p2, (40, 40, 230), thickness)
    if w > max_width:
        scale = max_width / w
        img = cv2.resize(img, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return buf.tobytes() if ok else None


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontName=FONT_BOLD, fontSize=20, leading=24, alignment=0),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName=FONT_BOLD, fontSize=13, leading=16, spaceBefore=10),
        "body": ParagraphStyle("b", parent=base["BodyText"], fontName=FONT, fontSize=10, leading=13),
        "small": ParagraphStyle("s", parent=base["BodyText"], fontName=FONT, fontSize=8.5, leading=11, textColor=colors.grey),
        "cell": ParagraphStyle("c", parent=base["BodyText"], fontName=FONT, fontSize=9, leading=11),
    }


def _fmt_dt(dt: datetime | None) -> str:
    return dt.astimezone().strftime("%d.%m.%Y %H:%M") if dt else "—"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_pdf(
    out_path: Path,
    *,
    title: str,
    created_at: datetime | None,
    duration_sec: float | None,
    findings: Iterable[dict],
    frames_dir: Path,
) -> Path:
    """Собирает PDF. `findings` — словари с полями контракта (`type, priority, confidence, timecode_sec,
    frame_path, bbox{x,y,w,h}|None, status`). Чистая функция без БД — удобно тестировать."""
    _register_fonts()
    st = _styles()
    items = list(findings)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
        title=f"Отчёт: {title}", author="LineSight AI",
    )
    story: list = [Paragraph("Отчёт об инспекции ЛЭП", st["title"]), Paragraph(_esc(title), st["h2"])]

    confirmed = sum(1 for f in items if f["status"] == "confirmed")
    rejected = sum(1 for f in items if f["status"] == "rejected")
    reshoot = sum(1 for f in items if f["status"] == "reshoot")
    dur = texts.fmt_timecode(duration_sec) if duration_sec else "—"
    meta = [
        [Paragraph("Дата инспекции", st["cell"]), Paragraph(_fmt_dt(created_at), st["cell"])],
        [Paragraph("Длительность видео", st["cell"]), Paragraph(dur, st["cell"])],
        [Paragraph("Находок всего", st["cell"]), Paragraph(str(len(items)), st["cell"])],
        [Paragraph("Подтверждено / отклонено / переснять", st["cell"]),
         Paragraph(f"{confirmed} / {rejected} / {reshoot}", st["cell"])],
    ]
    t = Table(meta, colWidths=[70 * mm, 100 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [Spacer(1, 4 * mm), t, Spacer(1, 6 * mm), Paragraph("Находки", st["h2"])]

    if not items:
        story.append(Paragraph("Находок нет.", st["body"]))
    else:
        rows = [[Paragraph(h, st["cell"]) for h in ("№", "Приоритет", "Тип", "Таймкод", "Уверенность", "Проверка")]]
        for i, f in enumerate(items, 1):
            color = PRIORITY_COLORS.get(f["priority"], colors.black).hexval()[2:]
            rows.append([
                Paragraph(str(i), st["cell"]),
                Paragraph(f'<font color="#{color}">{texts.PRIORITY_RU.get(f["priority"], f["priority"])}</font>', st["cell"]),
                Paragraph(_esc(texts.type_ru(f["type"])), st["cell"]),
                Paragraph(texts.fmt_timecode(f["timecode_sec"]), st["cell"]),
                Paragraph(f'{round(f["confidence"] * 100)}%', st["cell"]),
                Paragraph(texts.STATUS_RU.get(f["status"], f["status"]), st["cell"]),
            ])
        table = Table(rows, colWidths=[10 * mm, 32 * mm, 56 * mm, 22 * mm, 24 * mm, 28 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eceff1")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(table)

        story.append(Paragraph("Ключевые кадры", st["h2"]))
        for i, f in enumerate(items, 1):
            block: list = [
                Paragraph(f"<b>{i}. {_esc(texts.describe(f['type'], f['priority'], f['confidence'], f['timecode_sec']))}</b>", st["body"]),
                Paragraph(_esc(texts.recommendation(f["type"], f["priority"])), st["small"]),
            ]
            if f.get("frame_path"):
                bb = f.get("bbox")
                bbox = (bb["x"], bb["y"], bb["w"], bb["h"]) if bb else None
                jpeg = draw_bbox_jpeg(frames_dir / Path(f["frame_path"]).name, bbox)
                if jpeg:
                    w_mm = 120
                    arr = cv2.imdecode(np.frombuffer(jpeg, dtype="uint8"), cv2.IMREAD_COLOR)
                    ratio = arr.shape[0] / arr.shape[1]
                    block.append(Spacer(1, 1.5 * mm))
                    block.append(Image(io.BytesIO(jpeg), width=w_mm * mm, height=w_mm * ratio * mm))
            block.append(Spacer(1, 4 * mm))
            story.append(KeepTogether(block))

    story += [Spacer(1, 6 * mm), Paragraph(texts.DISCLAIMER + ".", st["small"])]
    doc.build(story)
    return out_path


def _needs_rebuild(report_file: Path, stamps: list[datetime | None]) -> bool:
    if not report_file.is_file():
        return True
    built = datetime.fromtimestamp(report_file.stat().st_mtime, tz=timezone.utc)
    for s in stamps:
        if s is None:
            continue
        s = s if s.tzinfo else s.replace(tzinfo=timezone.utc)
        if s > built:
            return True
    return False


def ensure_report(session, settings, inspection) -> Path:
    """Возвращает путь к актуальному PDF: создаёт при первом запросе, пересоздаёт при изменении решений."""
    from . import repository as repo, storage  # ленивый импорт: build_pdf не требует SQLAlchemy

    findings = repo.list_findings(session, inspection.id)
    report_file = storage.report_path(settings.data_dir, inspection.id)
    stamps = [inspection.finished_at] + [f.decided_at for f in findings]
    if _needs_rebuild(report_file, stamps):
        rows = [
            {
                "type": f.type, "priority": f.priority, "confidence": f.confidence, "timecode_sec": f.timecode_sec,
                "frame_path": f.frame_path, "status": f.status,
                "bbox": None if f.bbox_x is None else {"x": f.bbox_x, "y": f.bbox_y, "w": f.bbox_w, "h": f.bbox_h},
            }
            for f in findings
        ]
        build_pdf(
            report_file,
            title=inspection.title,
            created_at=repo.aware(inspection.created_at),
            duration_sec=inspection.duration_sec,
            findings=rows,
            frames_dir=storage.inspection_dir(settings.data_dir, inspection.id, create=False) / "frames",
        )
        log.info("Отчёт создан: %s", report_file)
    return report_file
