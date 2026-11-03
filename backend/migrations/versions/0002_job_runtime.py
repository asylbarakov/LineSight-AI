from alembic import op
import sqlalchemy as sa


revision = "0002_job_runtime"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "attempt_count",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "lease_token",
            sa.Uuid(),
            nullable=True,
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "model_name",
            sa.String(100),
            nullable=True,
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "model_version",
            sa.String(100),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_jobs_attempt_count",
        "jobs",
        "attempt_count >= 0",
    )

    op.add_column(
        "findings",
        sa.Column(
            "frame_index",
            sa.BigInteger(),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_findings_frame_index",
        "findings",
        "frame_index >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_findings_frame_index",
        "findings",
        type_="check",
    )

    op.drop_column("findings", "frame_index")

    op.drop_constraint(
        "ck_jobs_attempt_count",
        "jobs",
        type_="check",
    )

    op.drop_column("jobs", "model_version")
    op.drop_column("jobs", "model_name")
    op.drop_column("jobs", "heartbeat_at")
    op.drop_column("jobs", "lease_token")
    op.drop_column("jobs", "attempt_count")
