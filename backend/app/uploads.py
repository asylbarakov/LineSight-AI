
import json
import math
import os
import subprocess
import tempfile

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile


MAX_UPLOAD_BYTES = 512 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class StoredVideo:
    storage_key: str
    size_bytes: int
    duration_s: float
    fps: float | None
    width: int
    height: int


def inspect_mp4(
    path: Path,
) -> tuple[float, float | None, int, int]:

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries",
                "format=duration:stream=codec_type,width,height,avg_frame_rate",
                "-of", "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )

        metadata = json.loads(result.stdout)

        stream = next(
            s for s in metadata.get("streams", [])
            if s.get("codec_type") == "video"
        )

        duration = float(metadata["format"]["duration"])
        width = int(stream["width"])
        height = int(stream["height"])

        raw_fps = Fraction(
            stream.get("avg_frame_rate", "0/1")
        )
        fps = float(raw_fps) if raw_fps > 0 else None

        if (
            not math.isfinite(duration)
            or duration <= 0
            or width <= 0
            or height <= 0
        ):
            raise ValueError("Invalid video properties")

        return duration, fps, width, height

    except (
        subprocess.SubprocessError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        StopIteration,
        ZeroDivisionError,
    ) as exc:
        raise HTTPException(
            422, "Invalid or unreadable MP4 video"
        ) from exc


def store_mp4(
    upload: UploadFile,
    root: Path,
) -> StoredVideo:

    original_name = (
        (upload.filename or "")
        .replace("\\", "/")
        .split("/")[-1]
    )

    if not original_name.lower().endswith(".mp4"):
        raise HTTPException(
            415, "Only MP4 files are supported"
        )

    videos_dir = root / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=".upload-",
        suffix=".mp4",
        dir=videos_dir,
    )

    temp_path = Path(temp_name)
    size = 0

    try:
        with os.fdopen(fd, "wb") as dest:
            while chunk := upload.file.read(CHUNK_SIZE):
                size += len(chunk)

                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        413,
                        "Video is too large (512 MiB limit)",
                    )

                dest.write(chunk)

        with temp_path.open("rb") as source:
            header = source.read(12)

        if (
            len(header) < 12
            or header[4:8] != b"ftyp"
        ):
            raise HTTPException(
                422, "Not a valid MP4 container"
            )

        duration, fps, width, height = inspect_mp4(
            temp_path
        )

        storage_key = f"videos/{uuid4().hex}.mp4"

        os.replace(
            temp_path,
            root / storage_key,
        )

        return StoredVideo(
            storage_key,
            size,
            duration,
            fps,
            width,
            height,
        )

    finally:
        temp_path.unlink(missing_ok=True)
