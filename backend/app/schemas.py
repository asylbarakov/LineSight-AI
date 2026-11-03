from datetime import datetime
from math import isfinite
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InspectionOut(ORMResponse):
    id: UUID
    title: str
    created_at: datetime


class VideoOut(ORMResponse):
    id: UUID
    original_filename: str
    size_bytes: int
    duration_s: float | None
    fps: float | None
    width: int | None
    height: int | None


class JobOut(ORMResponse):
    id: UUID
    inspection_id: UUID
    status: str
    progress: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    attempt_count: int
    model_name: str | None
    model_version: str | None


class FindingOut(ORMResponse):
    id: UUID
    job_id: UUID
    category: str
    confidence: float | None
    timecode_s: float
    frame_index: int | None
    bbox: list[float] | None
    keyframe_key: str | None


class FindingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(
        min_length=1,
        max_length=100,
    )

    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        allow_inf_nan=False,
    )

    timecode_s: float = Field(
        ge=0,
        allow_inf_nan=False,
    )

    frame_index: int | None = Field(
        default=None,
        ge=0,
    )

    bbox: list[float] | None = None

    keyframe_key: str | None = Field(
        default=None,
        max_length=500,
    )

    @field_validator("bbox")
    @classmethod
    def validate_bbox(
        cls,
        value: list[float] | None,
    ) -> list[float] | None:

        if value is None:
            return None

        if len(value) != 4:
            raise ValueError(
                "bbox must contain exactly 4 coordinates"
            )

        if not all(
            isfinite(v) and 0 <= v <= 1
            for v in value
        ):
            raise ValueError(
                "bbox coordinates must be between 0 and 1"
            )

        x1, y1, x2, y2 = value

        if x1 >= x2 or y1 >= y2:
            raise ValueError(
                "Invalid bbox coordinate order"
            )

        return value


class ProcessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str = Field(
        min_length=1,
        max_length=100,
    )

    model_version: str = Field(
        min_length=1,
        max_length=100,
    )

    findings: list[FindingInput]


class InspectionDetail(InspectionOut):
    video: VideoOut | None
    jobs: list[JobOut]


class InspectionCreated(BaseModel):
    inspection_id: UUID
    job_id: UUID
    status: Literal["queued"]
