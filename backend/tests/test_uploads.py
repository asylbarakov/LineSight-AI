
from io import BytesIO

import pytest

from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app import uploads


def make_upload(name: str, content: bytes):
    return UploadFile(
        filename=name,
        file=BytesIO(content),
    )


def test_reject_wrong_extension(tmp_path):
    upload = make_upload(
        "example.txt",
        b"not a video",
    )

    with pytest.raises(HTTPException) as exc:
        uploads.store_mp4(upload, tmp_path)

    assert exc.value.status_code == 415


def test_reject_invalid_mp4(tmp_path):
    upload = make_upload(
        "example.mp4",
        b"not a valid mp4 file",
    )

    with pytest.raises(HTTPException) as exc:
        uploads.store_mp4(upload, tmp_path)

    assert exc.value.status_code == 422

    assert list((tmp_path / "videos").iterdir()) == []


def test_store_video_with_metadata(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        uploads,
        "inspect_mp4",
        lambda path: (12.5, 25.0, 1920, 1080),
    )

    upload = make_upload(
        "example.mp4",
        b"\x00\x00\x00\x18ftypisom" + b"test",
    )

    result = uploads.store_mp4(upload, tmp_path)

    assert result.duration_s == 12.5
    assert result.fps == 25.0
    assert result.width == 1920
    assert result.height == 1080

    assert (
        tmp_path / result.storage_key
    ).is_file()
