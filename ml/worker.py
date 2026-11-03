
import importlib
import logging
import os
import signal
import tempfile
from pathlib import Path
from threading import Event, Thread

import psycopg
from sqlalchemy import select

from app.database import new_session
from app.models import Video
from app.repositories import (
    claim_next_job,
    complete_job,
    fail_job,
    heartbeat_job,
    recover_stale_jobs,
)
from app.schemas import ProcessingResult


LOG = logging.getLogger("linesight.worker")
STOP = Event()


def check_database() -> bool:
    with psycopg.connect(
        host=os.getenv("DB_HOST", "postgres"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "linesight"),
        user=os.getenv("DB_USER", "linesight"),
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=2,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)


def check_storage() -> bool:
    root = Path(os.getenv("STORAGE_DIR", "/data"))
    if not root.is_dir():
        return False
    try:
        with tempfile.TemporaryFile(dir=root):
            pass
        return True
    except OSError:
        return False


def load_processor():
    module = importlib.import_module(
        os.getenv("JOB_PROCESSOR", "processor")
    )

    if not getattr(module, "READY", False):
        return None

    name = getattr(module, "MODEL_NAME", None)
    version = getattr(module, "MODEL_VERSION", None)

    if (
        not isinstance(name, str)
        or not 1 <= len(name) <= 100
        or not isinstance(version, str)
        or not 1 <= len(version) <= 100
        or not callable(getattr(module, "process_video", None))
    ):
        raise ValueError("Invalid ML processor contract")

    return module


def get_video_path(storage_key: str) -> Path:
    root = Path(
        os.getenv("STORAGE_DIR", "/data")
    ).resolve()

    videos_dir = (root / "videos").resolve()
    path = (root / storage_key).resolve()

    if (
        not path.is_relative_to(videos_dir)
        or not path.is_file()
    ):
        raise FileNotFoundError(
            "Video not found in shared storage"
        )

    return path


def send_heartbeats(
    job_id,
    lease_token,
    finished: Event,
) -> None:
    while not finished.wait(15):
        try:
            with new_session() as session:
                alive = heartbeat_job(
                    session,
                    job_id=job_id,
                    lease_token=lease_token,
                )
                session.commit()

            if not alive:
                LOG.warning(
                    "Job %s lost its lease",
                    job_id,
                )
                return

        except Exception:
            LOG.exception(
                "Heartbeat failed for job %s",
                job_id,
            )


def process_next_job(processor) -> bool:
    with new_session() as session:
        job = claim_next_job(
            session,
            model_name=processor.MODEL_NAME,
            model_version=processor.MODEL_VERSION,
        )

        if job is None:
            return False

        job_id = job.id
        lease_token = job.lease_token

        storage_key = session.scalar(
            select(Video.storage_key).where(
                Video.inspection_id == job.inspection_id
            )
        )

        session.commit()

    finished = Event()

    heartbeat_thread = Thread(
        target=send_heartbeats,
        args=(job_id, lease_token, finished),
        daemon=True,
    )
    heartbeat_thread.start()

    result = None
    error = None

    try:
        if storage_key is None:
            raise FileNotFoundError(
                "Inspection has no video"
            )

        path = get_video_path(storage_key)

        raw = processor.process_video(path)

        result = ProcessingResult.model_validate(raw)

    except Exception as exc:
        error = exc
        LOG.exception(
            "Processing failed for job %s",
            job_id,
        )

    finally:
        finished.set()
        heartbeat_thread.join(timeout=20)

    with new_session() as session:
        if error is None:
            accepted = complete_job(
                session,
                job_id=job_id,
                lease_token=lease_token,
                result=result,
            )
        else:
            accepted = fail_job(
                session,
                job_id=job_id,
                lease_token=lease_token,
                error_message=(
                    f"{type(error).__name__}: {error}"
                ),
            )

        session.commit()

    if accepted:
        LOG.info(
            "Job %s %s",
            job_id,
            "completed" if error is None else "failed",
        )
    else:
        LOG.warning(
            "Job %s changed owner; result discarded",
            job_id,
        )

    return True


def stop(signum: int, _frame: object) -> None:
    LOG.info("Received signal %s", signum)
    STOP.set()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s: %(message)s"
        ),
    )

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    processor = load_processor()

    if processor is None:
        LOG.warning(
            "No ML processor configured: "
            "queued jobs will not run"
        )
    else:
        LOG.info(
            "Processor ready: %s / %s",
            processor.MODEL_NAME,
            processor.MODEL_VERSION,
        )

    while not STOP.is_set():
        try:
            db_ok = check_database()
            storage_ok = check_storage()

            if not db_ok or not storage_ok:
                LOG.warning(
                    "Dependency check: "
                    "database=%s storage=%s",
                    db_ok,
                    storage_ok,
                )

            elif processor is not None:
                with new_session() as session:
                    requeued, failed = (
                        recover_stale_jobs(session)
                    )
                    session.commit()

                if requeued or failed:
                    LOG.warning(
                        "Recovered jobs: "
                        "requeued=%s failed=%s",
                        requeued,
                        failed,
                    )

                if process_next_job(processor):
                    continue

        except Exception:
            LOG.exception("Worker cycle failed")

        STOP.wait(15)

    LOG.info("Worker stopped")


if __name__ == "__main__":
    main()
