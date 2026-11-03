"""Хранение файлов инспекций (задача 28): `data/inspections/<id>/{video.mp4, frames/, report.pdf}`.

В БД хранятся только относительные пути. Все пути проверяются на выход за пределы папки.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import BinaryIO

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_FRAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.jpg$")
CHUNK = 1024 * 1024


class FileTooLarge(Exception):
    pass


class UnsafePath(ValueError):
    pass


def safe_join(base: Path, *parts: str) -> Path:
    """Склеивает путь и проверяет, что результат остался внутри `base`."""
    base = Path(base).resolve()
    target = base.joinpath(*parts).resolve()
    if target != base and base not in target.parents:
        raise UnsafePath(f"Путь выходит за пределы {base}")
    return target


def inspections_root(data_dir: str) -> Path:
    root = Path(data_dir) / "inspections"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def inspection_dir(data_dir: str, inspection_id: str, create: bool = True) -> Path:
    """`data/inspections/<id>/` (с подпапкой `frames/`). id должен быть uuid."""
    if not _UUID_RE.match(inspection_id):
        raise UnsafePath("Некорректный идентификатор инспекции")
    path = safe_join(inspections_root(data_dir), inspection_id)
    if create:
        (path / "frames").mkdir(parents=True, exist_ok=True)
    return path


def video_path(data_dir: str, inspection_id: str) -> Path:
    return inspection_dir(data_dir, inspection_id, create=False) / "video.mp4"


def report_path(data_dir: str, inspection_id: str) -> Path:
    return inspection_dir(data_dir, inspection_id, create=False) / "report.pdf"


def frame_file(data_dir: str, inspection_id: str, name: str) -> Path:
    if not _FRAME_RE.match(name):
        raise UnsafePath("Некорректное имя кадра")
    return safe_join(inspection_dir(data_dir, inspection_id, create=False), "frames", name)


def resolve_relative(data_dir: str, inspection_id: str, rel_path: str) -> Path:
    """Относительный путь из БД (`frames/x.jpg`) → абсолютный, с проверкой границ."""
    return safe_join(inspection_dir(data_dir, inspection_id, create=False), rel_path)


def save_stream(src: BinaryIO, dest: Path, max_bytes: int) -> int:
    """Пишет поток на диск по частям. Если размер больше лимита — удаляет файл и бросает FileTooLarge."""
    written = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as out:
        while True:
            chunk = src.read(CHUNK)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                raise FileTooLarge(f"Файл больше {max_bytes} байт")
            out.write(chunk)
    return written


def delete_inspection_dir(data_dir: str, inspection_id: str) -> None:
    path = inspection_dir(data_dir, inspection_id, create=False)
    shutil.rmtree(path, ignore_errors=True)
