from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inspections",
        sa.Column(
            "id", sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "videos",
        sa.Column(
            "id", sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "inspection_id", sa.Uuid(),
            sa.ForeignKey(
                "inspections.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "original_filename", sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "storage_key", sa.String(500),
            nullable=False,
        ),
        sa.Column(
            "size_bytes", sa.BigInteger(),
            nullable=False,
        ),
        sa.Column("duration_s", sa.Float()),
        sa.Column("fps", sa.Float()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.UniqueConstraint(
            "inspection_id",
            name="uq_videos_inspection_id",
        ),
        sa.UniqueConstraint(
            "storage_key",
            name="uq_videos_storage_key",
        ),
        sa.CheckConstraint(
            "size_bytes > 0",
            name="ck_videos_size_positive",
        ),
    )

    op.create_table(
        "jobs",
        sa.Column(
            "id", sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "inspection_id", sa.Uuid(),
            sa.ForeignKey(
                "inspections.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(20),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column(
            "progress", sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True),
        ),
        sa.Column(
            "finished_at", sa.DateTime(timezone=True),
        ),
        sa.Column("error_message", sa.String(1000)),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'done', 'failed')",
            name="ck_jobs_status",
        ),
        sa.CheckConstraint(
            "progress BETWEEN 0 AND 100",
            name="ck_jobs_progress",
        ),
    )

    op.create_index(
        "ix_jobs_inspection_id",
        "jobs",
        ["inspection_id"],
    )
    op.create_index(
        "ix_jobs_status_created_at",
        "jobs",
        ["status", "created_at"],
    )

    op.create_table(
        "findings",
        sa.Column(
            "id", sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "job_id", sa.Uuid(),
            sa.ForeignKey(
                "jobs.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "category", sa.String(100),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float()),
        sa.Column(
            "timecode_s", sa.Float(),
            nullable=False,
        ),
        sa.Column("bbox", JSONB()),
        sa.Column("keyframe_key", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_findings_confidence",
        ),
        sa.CheckConstraint(
            "timecode_s >= 0",
            name="ck_findings_timecode",
        ),
    )

    op.create_index(
        "ix_findings_job_id",
        "findings",
        ["job_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_findings_job_id", table_name="findings"
    )
    op.drop_table("findings")

    op.drop_index(
        "ix_jobs_status_created_at", table_name="jobs"
    )
    op.drop_index(
        "ix_jobs_inspection_id", table_name="jobs"
    )
    op.drop_table("jobs")
    op.drop_table("videos")
    op.drop_table("inspections")
