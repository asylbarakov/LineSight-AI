"""Inspect a supplied ZIP by default. Network access requires --download."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import stat
import tempfile
import zipfile

REPO_ID = "sxiong/Power-equipment-image-dataset"
FILENAME = "transmission line object detection.zip"
DATA_DIR = Path(__file__).resolve().parent / "data"


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_members(archive, max_bytes=4 * 1024**3, max_members=100000):
    members = archive.infolist()
    if len(members) > max_members or sum(item.file_size for item in members) > max_bytes:
        raise ValueError("Archive exceeds member count or uncompressed size limit")
    seen = set()
    for item in members:
        name = item.orig_filename
        posix = PurePosixPath(name)
        windows = PureWindowsPath(name)
        if (not name or name != item.filename or "\\" in name or posix.is_absolute() or windows.drive
                or any(ord(char) < 32 for char in name)
                or any(part in ("", ".", "..") for part in name.rstrip("/").split("/"))
                or any(":" in part or part.endswith((".", " ")) for part in posix.parts)
                or any(PureWindowsPath(part).is_reserved() for part in posix.parts)):
            raise ValueError(f"Unsafe archive path: {name!r}")
        mode = item.external_attr >> 16
        if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
            raise ValueError(f"Unsupported archive entry: {name!r}")
        key = name.rstrip("/").casefold()
        if key in seen:
            raise ValueError(f"Duplicate/case-colliding archive path: {name!r}")
        seen.add(key)
        if item.flag_bits & 1:
            raise ValueError("Encrypted archives are not supported")
    return members


def inspect_archive(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("Archive is missing or empty")
    with zipfile.ZipFile(path) as archive:
        members = checked_members(archive)
        return {
            "archive": str(path.resolve()), "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path), "entries": len(members),
            "uncompressed_bytes": sum(item.file_size for item in members),
            "extensions": dict(Counter(PurePosixPath(item.filename).suffix.lower() for item in members if not item.is_dir())),
            "first_50_paths": [item.filename for item in members[:50]],
        }


def safe_extract(path, destination, max_bytes=4 * 1024**3):
    """Extract to a NEW directory via staging; never merge into existing files."""
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination must not exist: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".extract-", dir=destination.parent))
    try:
        with zipfile.ZipFile(path) as archive:
            members = checked_members(archive, max_bytes=max_bytes)
            required = sum(item.file_size for item in members) + 256 * 1024**2
            if shutil.disk_usage(staging).free < required:
                raise OSError(f"Insufficient free disk space: need {required} bytes including reserve")
            for item in members:
                target = staging.joinpath(*PurePosixPath(item.filename).parts)
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
        # Windows rename refuses an existing destination. Reserve on other platforms too.
        destination.mkdir(exist_ok=False)
        try:
            for child in staging.iterdir():
                child.rename(destination / child.name)
        except Exception:
            shutil.rmtree(destination)
            raise
        return destination
    finally:
        shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--archive", type=Path, help="Existing local ZIP; no network")
    source.add_argument("--download", action="store_true", help="Explicitly download only the target ZIP")
    parser.add_argument("--revision", help="HF dataset commit SHA (or explicitly main); required with --download")
    parser.add_argument("--cache-dir", type=Path, default=DATA_DIR / "hf-cache")
    parser.add_argument("--extract-to", type=Path, help="Optional NEW extraction directory")
    args = parser.parse_args()
    if args.download:
        if not args.revision:
            parser.error("--download requires --revision; prefer a dataset commit SHA")
        from huggingface_hub import hf_hub_download
        path = Path(hf_hub_download(repo_id=REPO_ID, repo_type="dataset", filename=FILENAME,
                                    revision=args.revision, cache_dir=str(args.cache_dir)))
    else:
        path = args.archive
    report = inspect_archive(path)
    report.update({"dataset_id": REPO_ID if args.download else None,
                   "requested_revision": args.revision if args.download else None})
    if args.extract_to:
        report["extracted_to"] = str(safe_extract(path, args.extract_to))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
