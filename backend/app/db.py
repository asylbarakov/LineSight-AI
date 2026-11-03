"""Модели БД и подключение (задача 27). SQLAlchemy 2.0, PostgreSQL (в тестах — SQLite).

НЕ ПРОВЕРЕНО в песочнице разработки (там нет SQLAlchemy): запустите `pytest backend/tests`.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

log = logging.getLogger("linesight.db")

STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

FINDING_NEW = "new"
FINDING_CONFIRMED = "confirmed"
FINDING_REJECTED = "rejected"
FINDING_RESHOOT = "reshoot"
DECISIONS = (FINDING_CONFIRMED, FINDING_REJECTED, FINDING_RESHOOT)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default=STATUS_QUEUED, index=True)
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    stage_times: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    findings: Mapped[list["Finding"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan", passive_deletes=True
    )


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (UniqueConstraint("inspection_id", "track_id", "type", name="uq_finding_track_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    inspection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inspections.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(128))
    priority: Mapped[str] = mapped_column(String(24))
    confidence: Mapped[float] = mapped_column(Float)
    timecode_sec: Mapped[float] = mapped_column(Float)
    frame_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bbox_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=FINDING_NEW)
    track_id: Mapped[int] = mapped_column(Integer)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    inspection: Mapped[Inspection] = relationship(back_populates="findings")


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine, retries: int = 30, delay_sec: float = 1.0) -> None:
    """Создаёт таблицы. При старте контейнеров Postgres может быть ещё недоступен — ждём."""
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(engine)
            return
        except OperationalError as exc:
            if attempt == retries:
                raise
            log.warning("БД недоступна (попытка %s/%s): %s", attempt, retries, exc.__cause__ or exc)
            time.sleep(delay_sec)
