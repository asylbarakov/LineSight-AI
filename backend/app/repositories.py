from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .models import Finding, Inspection, Job, Video
from .schemas import ProcessingResult

def create_inspection(
    session: Session,
    *,
    title: str,
    filename: str,
    storage_key: str,
    size_bytes: int,
) -> tuple[Inspection, Job]:
    inspection = Inspection(title=title)

    session.add(inspection)
    session.flush()

    video = Video(
        inspection_id=inspection.id,
        original_filename=filename,
        storage_key=storage_key,
        size_bytes=size_bytes,
    )

    job = Job(inspection_id=inspection.id)

    session.add_all([video, job])
    session.flush()

    return inspection, job


def claim_next_job(session: Session, *, model_name: str, model_version: str,) -> Job | None:
    statement = (
        select(Job)
        .where(Job.status == "queued")
        .order_by(Job.created_at, Job.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    job = session.scalars(statement).first()

    if job is None:
        return None

    now = datetime.now(timezone.utc)

    job.status = "processing"
    job.attempt_count += 1
    job.lease_token = uuid4()
    job.heartbeat_at = now
    job.started_at = now
    job.finished_at = None
    job.progress = 0
    job.error_message = None
    job.model_name = model_name
    job.model_version = model_version

    return job


def heartbeat_job(session: Session, *, job_id: UUID, lease_token: UUID,):
    statement = (
        update(Job)
        .where(
            Job.id == job_id,
            Job.status == "processing",
            Job.lease_token == lease_token,
        )
        .values(
            heartbeat_at=datetime.now(timezone.utc)
        )
    )

    return session.execute(statement).rowcount == 1


def _owned_job(session: Session, *, job_id: UUID, lease_token: UUID,) -> Job | None:
    return session.scalar(
        select(Job)
        .where(
            Job.id == job_id,
            Job.status == "processing",
            Job.lease_token == lease_token,
        )
        .with_for_update()
    )

def complete_job(session: Session, *, job_id: UUID, lease_token: UUID, result: ProcessingResult,):
    result = ProcessingResult.model_validate(result)

    job = _owned_job(
        session,
        job_id=job_id,
        lease_token=lease_token,
    )

    if job is None:
        return False

    if (
        result.model_name != job.model_name
        or result.model_version != job.model_version
    ):
        raise ValueError(
            "The result model differs from the claimed model"
        )

    for item in result.findings:
        session.add(
            Finding(
                job_id=job.id,
                **item.model_dump(),
            )
        )

    job.status = "done"
    job.progress = 100
    job.finished_at = datetime.now(timezone.utc)

    job.lease_token = None
    job.heartbeat_at = None
    job.error_message = None

    session.flush()
    return True


def fail_job(session: Session, *, job_id: UUID, lease_token: UUID, error_message: str,):
    job = _owned_job(
        session,
        job_id=job_id,
        lease_token=lease_token,
    )

    if job is None:
        return False

    job.status = "failed"
    job.finished_at = datetime.now(timezone.utc)
    job.error_message = (
        error_message or "Unknown error"
    )[:1000]

    job.lease_token = None
    job.heartbeat_at = None

    return True


def recover_stale_jobs(session: Session, *, timeout_seconds: int = 300, max_attempts: int = 3, batch_size: int = 100,) -> tuple[int, int]:
    if (
        timeout_seconds <= 0
        or max_attempts < 1
        or batch_size < 1
    ):
        raise ValueError("Invalid recovery parameters")

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(seconds=timeout_seconds)
    )

    statement = (
        select(Job)
        .where(
            Job.status == "processing",
            func.coalesce(
                Job.heartbeat_at,
                Job.started_at,
                Job.created_at,
            ) < cutoff,
        )
        .order_by(Job.created_at, Job.id)
        .with_for_update(skip_locked=True)
        .limit(batch_size)
    )

    stale_jobs = session.scalars(statement).all()

    requeued = 0
    failed = 0

    for job in stale_jobs:
        job.lease_token = None
        job.heartbeat_at = None

        if job.attempt_count >= max_attempts:
            job.status = "failed"
            job.finished_at = datetime.now(
                timezone.utc
            )
            job.error_message = (
                "Worker heartbeat timeout: "
                "retry limit reached"
            )
            failed += 1

        else:
            job.status = "queued"
            job.progress = 0
            job.started_at = None
            job.finished_at = None
            job.error_message = None
            requeued += 1

    return requeued, failed
