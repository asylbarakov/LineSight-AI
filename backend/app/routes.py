
import logging

from collections.abc import Generator
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import new_session
from .models import Finding, Inspection, Job, Video
from .repositories import create_inspection
from .schemas import (
    FindingOut,
    InspectionCreated,
    InspectionDetail,
    InspectionOut,
    JobOut,
)
from .uploads import store_mp4


logger = logging.getLogger(__name__)
router = APIRouter(tags=["inspections"])


def get_session() -> Generator[Session, None, None]:
    with new_session() as session:
        yield session


@router.post(
    "/inspections",
    status_code=201,
    response_model=InspectionCreated,
)
def upload_inspection(
    title: Annotated[
        str, Form(min_length=1, max_length=200)
    ],
    file: Annotated[UploadFile, File()],
    session: Annotated[Session, Depends(get_session)],
):
    root = get_settings().storage_dir
    saved = store_mp4(file, root)

    filename = (
        (file.filename or "")
        .replace("\\", "/")
        .split("/")[-1]
    )

    try:
        inspection, job = create_inspection(
            session,
            title=title,
            filename=filename,
            storage_key=saved.storage_key,
            size_bytes=saved.size_bytes,
        )

        video = session.scalar(
            select(Video).where(
                Video.inspection_id == inspection.id
            )
        )

        if video is None:
            raise RuntimeError("Video record missing")

        video.duration_s = saved.duration_s
        video.fps = saved.fps
        video.width = saved.width
        video.height = saved.height

        session.flush()

        inspection_id = inspection.id
        job_id = job.id

        session.commit()

    except Exception:
        session.rollback()
        (root / saved.storage_key).unlink(
            missing_ok=True
        )
        logger.exception("Could not create inspection")
        raise

    finally:
        file.file.close()

    return InspectionCreated(
        inspection_id=inspection_id,
        job_id=job_id,
        status="queued",
    )


@router.get(
    "/inspections",
    response_model=list[InspectionOut],
)
def list_inspections(
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = (
        select(Inspection)
        .order_by(
            Inspection.created_at.desc(),
            Inspection.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    return session.scalars(stmt).all()


@router.get(
    "/inspections/{inspection_id}",
    response_model=InspectionDetail,
)
def inspection_detail(
    inspection_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    inspection = session.get(
        Inspection, inspection_id
    )

    if inspection is None:
        raise HTTPException(
            404, "Inspection not found"
        )

    video = session.scalar(
        select(Video).where(
            Video.inspection_id == inspection_id
        )
    )

    jobs = session.scalars(
        select(Job)
        .where(Job.inspection_id == inspection_id)
        .order_by(
            Job.created_at.desc(),
            Job.id.desc(),
        )
    ).all()

    return InspectionDetail(
        id=inspection.id,
        title=inspection.title,
        created_at=inspection.created_at,
        video=video,
        jobs=jobs,
    )


@router.get("/inspections/{inspection_id}/video")
def inspection_video(
    inspection_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    video = session.scalar(
        select(Video).where(
            Video.inspection_id == inspection_id
        )
    )

    if video is None:
        raise HTTPException(
            404, "Video not found"
        )

    root = get_settings().storage_dir.resolve()
    path = (root / video.storage_key).resolve()

    if not path.is_relative_to(root / "videos"):
        raise HTTPException(
            404, "Video not found"
        )

    if not path.is_file():
        raise HTTPException(
            404, "Video file missing"
        )

    return FileResponse(
        path,
        media_type="video/mp4",
        filename=video.original_filename,
        content_disposition_type="inline",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobOut,
)
def job_detail(
    job_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    job = session.get(Job, job_id)

    if job is None:
        raise HTTPException(404, "Job not found")

    return job


@router.get(
    "/inspections/{inspection_id}/findings",
    response_model=list[FindingOut],
)
def inspection_findings(
    inspection_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    job_id: UUID | None = None,
):
    if session.get(Inspection, inspection_id) is None:
        raise HTTPException(
            404, "Inspection not found"
        )

    stmt = (
        select(Finding)
        .join(Job, Finding.job_id == Job.id)
        .where(Job.inspection_id == inspection_id)
        .order_by(
            Finding.timecode_s,
            Finding.id,
        )
    )

    if job_id is not None:
        stmt = stmt.where(
            Finding.job_id == job_id
        )

    return session.scalars(stmt).all()
