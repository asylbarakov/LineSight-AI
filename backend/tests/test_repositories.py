from unittest.mock import Mock
from uuid import uuid4

from app import repositories as repo
from app.models import Job
from app.schemas import FindingInput, ProcessingResult


def test_claim_assigns_lease_and_attempt():
    session = Mock()
    job = Job(status="queued", attempt_count=0)
    session.scalars.return_value.first.return_value = job

    claimed = repo.claim_next_job(
        session,
        model_name="detector",
        model_version="v1",
    )

    assert claimed is job
    assert job.status == "processing"
    assert job.attempt_count == 1
    assert job.lease_token is not None
    assert job.heartbeat_at is not None
    assert job.model_name == "detector"


def test_claim_when_queue_empty():
    session = Mock()
    session.scalars.return_value.first.return_value = None

    result = repo.claim_next_job(
        session,
        model_name="test",
        model_version="v1",
    )

    assert result is None


def test_complete_stores_finding(monkeypatch):
    job = Job(
        id=uuid4(),
        status="processing",
        model_name="detector",
        model_version="v1",
        lease_token=uuid4(),
        attempt_count=1,
    )

    monkeypatch.setattr(
        repo,
        "_owned_job",
        lambda *args, **kwargs: job,
    )

    session = Mock()

    result = ProcessingResult(
        model_name="detector",
        model_version="v1",
        findings=[
            FindingInput(
                category="crack",
                timecode_s=2.5,
                bbox=[0.1, 0.2, 0.3, 0.4],
            )
        ],
    )

    assert repo.complete_job(
        session,
        job_id=job.id,
        lease_token=job.lease_token,
        result=result,
    )

    assert job.status == "done"
    assert job.progress == 100
    assert job.lease_token is None
    assert session.add.call_count == 1
    assert session.flush.called


def test_fail_clears_ownership(monkeypatch):
    job = Job(
        id=uuid4(),
        status="processing",
        lease_token=uuid4(),
    )

    monkeypatch.setattr(
        repo,
        "_owned_job",
        lambda *args, **kwargs: job,
    )

    session = Mock()

    assert repo.fail_job(
        session,
        job_id=job.id,
        lease_token=job.lease_token,
        error_message="boom",
    )

    assert job.status == "failed"
    assert job.error_message == "boom"
    assert job.lease_token is None


def test_recover_stale_jobs():
    session = Mock()

    retry = Job(
        status="processing",
        attempt_count=1,
        lease_token=uuid4(),
    )

    exhausted = Job(
        status="processing",
        attempt_count=3,
        lease_token=uuid4(),
    )

    session.scalars.return_value.all.return_value = [
        retry,
        exhausted,
    ]

    result = repo.recover_stale_jobs(
        session,
        max_attempts=3,
    )

    assert result == (1, 1)
    assert retry.status == "queued"
    assert retry.lease_token is None
    assert exhausted.status == "failed"
