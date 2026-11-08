"""Операции с БД: инспекции, находки, очередь, метрики (задачи 32–36).

НЕ ПРОВЕРЕНО в песочнице разработки (там нет SQLAlchemy): запустите `pytest backend/tests`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import case, func, select, update
from .defect_policy import is_equipment_defect
from sqlalchemy.orm import Session

from .db import (
    DECISIONS,
    FINDING_NEW,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PROCESSING,
    STATUS_QUEUED,
    Finding,
    Inspection,
    utcnow,
)

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, "insufficient_data": 3}


def aware(dt: datetime | None) -> datetime | None:
    """SQLite возвращает даты без часового пояса — считаем их UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ---------- инспекции ----------

def create_inspection(session: Session, inspection_id: str, title: str, filename: str, duration_sec: float | None) -> Inspection:
    insp = Inspection(id=inspection_id, title=title, filename=filename, status=STATUS_QUEUED, duration_sec=duration_sec)
    session.add(insp)
    session.commit()
    return insp


def get_inspection(session: Session, inspection_id: str) -> Inspection | None:
    return session.get(Inspection, inspection_id)


def list_inspections(session: Session) -> list[tuple[Inspection, int]]:
    """Инспекции по убыванию даты вместе с числом находок."""
    counts = (
        select(Finding.inspection_id, func.count(Finding.id).label("n")).group_by(Finding.inspection_id).subquery()
    )
    rows = session.execute(
        select(Inspection, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.inspection_id == Inspection.id)
        .order_by(Inspection.created_at.desc())
    ).all()
    return [(insp, int(n)) for insp, n in rows]


def delete_inspection(session: Session, inspection_id: str) -> bool:
    insp = session.get(Inspection, inspection_id)
    if insp is None:
        return False
    session.delete(insp)
    session.commit()
    return True


# ---------- очередь ----------

def claim_next(session: Session) -> Inspection | None:
    """Атомарно берёт самую старую задачу `queued` и переводит её в `processing`.

    В PostgreSQL `FOR UPDATE SKIP LOCKED` не даёт двум воркерам взять одну задачу; дополнительно
    `UPDATE … WHERE status='queued'` защищает от гонки в любой БД.
    """
    row = session.execute(
        select(Inspection.id)
        .where(Inspection.status == STATUS_QUEUED)
        .order_by(Inspection.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if row is None:
        session.rollback()
        return None
    result = session.execute(
        update(Inspection)
        .where(Inspection.id == row[0], Inspection.status == STATUS_QUEUED)
        .values(status=STATUS_PROCESSING, started_at=utcnow(), progress=0.0, error_code=None, error_message=None)
    )
    session.commit()
    if result.rowcount == 0:
        return None
    return session.get(Inspection, row[0], populate_existing=True)


def requeue(session: Session, inspection_id: str) -> None:
    """Вернуть инспекцию в очередь (повторная обработка)."""
    session.execute(
        update(Inspection)
        .where(Inspection.id == inspection_id)
        .values(status=STATUS_QUEUED, error_code=None, error_message=None, progress=0.0, finished_at=None)
    )
    session.commit()


def set_progress(session: Session, inspection_id: str, progress: float) -> None:
    session.execute(update(Inspection).where(Inspection.id == inspection_id).values(progress=round(progress, 3)))
    session.commit()


def mark_done(
    session: Session, inspection_id: str, duration_sec: float, fps: float, stage_times: dict[str, float]
) -> None:
    session.execute(
        update(Inspection)
        .where(Inspection.id == inspection_id)
        .values(
            status=STATUS_DONE,
            progress=1.0,
            duration_sec=duration_sec,
            fps=fps,
            stage_times=stage_times,
            finished_at=utcnow(),
            error_code=None,
            error_message=None,
        )
    )
    session.commit()


def mark_failed(session: Session, inspection_id: str, code: str, message: str) -> None:
    session.execute(
        update(Inspection)
        .where(Inspection.id == inspection_id)
        .values(status=STATUS_FAILED, error_code=code, error_message=message[:1000], finished_at=utcnow())
    )
    session.commit()


def fail_stale(session: Session, older_than_sec: float, code: str = "E_TIMEOUT") -> int:
    """Задачи, зависшие в `processing` (воркер упал), помечаются `failed`."""
    limit = utcnow() - timedelta(seconds=older_than_sec)
    stale = [
        i
        for i in session.execute(select(Inspection).where(Inspection.status == STATUS_PROCESSING)).scalars()
        if (aware(i.started_at) or utcnow()) < limit
    ]
    for insp in stale:
        insp.status = STATUS_FAILED
        insp.error_code = code
        insp.error_message = "Обработка прервана: воркер не завершил задачу"
        insp.finished_at = utcnow()
    session.commit()
    return len(stale)


# ---------- находки ----------

@dataclass
class FindingInput:
    type: str
    priority: str
    confidence: float
    timecode_sec: float
    track_id: int
    frame_path: str | None = None
    bbox: tuple[float, float, float, float] | None = None


def save_findings(session: Session, inspection_id: str, findings: Iterable[FindingInput]) -> int:
    """Записывает находки одной транзакцией, без дублей (задача 34).

    - ключ `(inspection_id, track_id, type)`: существующая находка обновляется, а не дублируется;
    - решения инженера (`confirmed`, `rejected`, `reshoot`) не затираются;
    - необработанные находки (`new`) прошлого прогона, которых нет в новом, удаляются.

    Возвращает число находок инспекции после записи.
    """
    incoming = {(f.track_id, f.type): f for f in findings}
    try:
        existing = {
            (f.track_id, f.type): f
            for f in session.execute(select(Finding).where(Finding.inspection_id == inspection_id)).scalars()
        }
        for key, f in incoming.items():
            row = existing.get(key)
            if row is None:
                row = Finding(inspection_id=inspection_id, type=f.type, track_id=f.track_id, status=FINDING_NEW)
                session.add(row)
            elif row.status != FINDING_NEW:
                continue  # решение инженера важнее перезаписи
            row.priority = f.priority
            row.confidence = f.confidence
            row.timecode_sec = f.timecode_sec
            row.frame_path = f.frame_path
            if f.bbox is None:
                row.bbox_x = row.bbox_y = row.bbox_w = row.bbox_h = None
            else:
                row.bbox_x, row.bbox_y, row.bbox_w, row.bbox_h = f.bbox
        for key, row in existing.items():
            if key not in incoming and row.status == FINDING_NEW:
                session.delete(row)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return session.execute(
        select(func.count(Finding.id)).where(Finding.inspection_id == inspection_id)
    ).scalar_one()


def list_findings(session: Session, inspection_id: str) -> list[Finding]:
    """Находки: приоритет (high → insufficient_data), затем таймкод."""
    rows = list(session.execute(select(Finding).where(Finding.inspection_id == inspection_id)).scalars())
    rows.sort(key=lambda f: (PRIORITY_ORDER.get(f.priority, 99), f.timecode_sec))
    return rows


def get_finding(session: Session, finding_id: str) -> Finding | None:
    return session.get(Finding, finding_id)


def set_finding_status(session: Session, finding_id: str, status: str) -> Finding | None:
    """Решение инженера. Допустимы только `confirmed|rejected|reshoot`; менять можно повторно."""
    if status not in DECISIONS:
        raise ValueError(f"Недопустимый статус: {status}")
    finding = session.get(Finding, finding_id)
    if finding is None:
        return None
    finding.status = status
    finding.decided_at = utcnow()
    session.commit()
    return finding


# ---------- метрики ----------

def metrics(session: Session, recent: int = 10) -> dict:
    total = session.execute(select(func.count(Inspection.id))).scalar_one()
    # Aggregate persisted rows in SQL, then classify the small set of type buckets
    # using the equipment taxonomy (ML scoring also includes hazards).
    # No finding entities are loaded; priority is not a semantic category.
    buckets = session.execute(
        select(Finding.type, func.count(Finding.id),
               func.sum(case((Finding.status == "confirmed", 1), else_=0)))
        .group_by(Finding.type)
    ).all()
    detected = confirmed = 0
    for finding_type, count, approved in buckets:
        if is_equipment_defect(finding_type):
            detected += count
            confirmed += approved
    failed = session.execute(
        select(func.count(Inspection.id)).where(Inspection.status == STATUS_FAILED)
    ).scalar_one()
    done = list(session.execute(select(Inspection).where(Inspection.status == STATUS_DONE)).scalars())
    times = [
        (aware(i.finished_at) - aware(i.started_at)).total_seconds()
        for i in done
        if i.started_at is not None and i.finished_at is not None
    ]
    fps_values = [i.fps for i in done if i.fps]
    runs = list(
        session.execute(
            select(Inspection)
            .where(Inspection.status.in_([STATUS_DONE, STATUS_FAILED]))
            .order_by(Inspection.finished_at.desc())
            .limit(recent)
        ).scalars()
    )
    return {
        "inspections_total": total,
        "detected_defects_total": int(detected),
        "confirmed_defects_total": int(confirmed),
        "avg_processing_sec": round(sum(times) / len(times), 2) if times else None,
        "avg_fps": round(sum(fps_values) / len(fps_values), 2) if fps_values else None,
        "failed_share": round(failed / total, 3) if total else 0.0,
        "recent_runs": [
            {
                "id": r.id,
                "title": r.title,
                "status": r.status,
                "error_code": r.error_code,
                "fps": r.fps,
                "stage_times": r.stage_times,
            }
            for r in runs
        ],
    }
