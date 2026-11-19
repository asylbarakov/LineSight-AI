from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime,
    Float, ForeignKey, Index, SmallInteger,
    String, UniqueConstraint, Uuid, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship,
)


class Base(DeclarativeBase):
    pass


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    video: Mapped["Video | None"] = relationship(
        back_populates="inspection",
        uselist=False,
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="inspection",
    )


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        UniqueConstraint(
            "inspection_id",
            name="uq_videos_inspection_id",
        ),
        UniqueConstraint(
            "storage_key",
            name="uq_videos_storage_key",
        ),
        CheckConstraint(
            "size_bytes > 0",
            name="ck_videos_size_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    inspection_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inspections.id", ondelete="CASCADE"),
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    duration_s: Mapped[float | None] = mapped_column(Float)
    fps: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None]
    height: Mapped[int | None]

    inspection: Mapped[Inspection] = relationship(
        back_populates="video",
    )


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'processing', 'done', 'failed')",
            name="ck_jobs_status",
        ),
        CheckConstraint(
            "progress BETWEEN 0 AND 100",
            name="ck_jobs_progress",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_jobs_attempt_count",),
        Index("ix_jobs_status_created_at", "status", "created_at"),
        Index("ix_jobs_inspection_id", "inspection_id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    inspection_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inspections.id", ondelete="CASCADE"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'queued'"),
    )
    progress: Mapped[int] = mapped_column(
        SmallInteger,
        server_default=text("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    error_message: Mapped[str | None] = mapped_column(String(1000))

    attempt_count: Mapped[int] = mapped_column(
        SmallInteger,
        server_default=text("0"),
    )

    lease_token: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
    )

    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    model_name: Mapped[str | None] = mapped_column(
        String(100),
    )

    model_version: Mapped[str | None] = mapped_column(
        String(100),
    )

    inspection: Mapped[Inspection] = relationship(
        back_populates="jobs",
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="job",
    )


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_findings_confidence",
        ),
        CheckConstraint(
            "timecode_s >= 0",
            name="ck_findings_timecode",
        ),
        CheckConstraint(
            "frame_index >= 0",
            name="ck_findings_frame_index",
        ),
        Index("ix_findings_job_id", "job_id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
    )
    category: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)
    timecode_s: Mapped[float] = mapped_column(Float)
    frame_index: Mapped[int | None] = mapped_column(
        BigInteger,
    )
    bbox: Mapped[list[float] | None] = mapped_column(JSONB)
    keyframe_key: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    job: Mapped[Job] = relationship(
        back_populates="findings",
    )
