"""First-pass dataset inventory. Annotation semantics require real-sample review.

No implicit YOLO/COCO/VOC assumptions; source files are never modified.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import hashlib
import math
from pathlib import Path
import platform
import subprocess
import xml.etree.ElementTree as ET

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
CANDIDATE_EXTENSIONS = {".xml", ".json", ".txt", ".csv", ".yaml", ".yml"}


def validate_bbox(box, width, height):
    """Validate explicit pixel xyxy (no guessing, clipping or source conversion)."""
    if len(box) != 4 or not all(math.isfinite(v) for v in (*box, width, height)):
        raise ValueError("Expected four finite xyxy coordinates and finite dimensions")
    x1, y1, x2, y2 = box
    if not (width > 0 and height > 0 and 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("BBox outside image, empty or reversed")
    return {"width_px": x2 - x1, "height_px": y2 - y1,
            "relative_width": (x2 - x1) / width,
            "relative_height": (y2 - y1) / height,
            "relative_area": (x2 - x1) * (y2 - y1) / (width * height)}


def annotation_probe(path):
    """Show syntax evidence, never infer dataset labels from arbitrary text files."""
    if path.stat().st_size > 1024 * 1024:
        return {"status": "not_probed", "reason": "over 1 MiB; inspect explicitly after inventory"}
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        value = json.loads(text)
        result = {"syntax": "json", "root_type": type(value).__name__}
        if isinstance(value, dict):
            result["top_level_keys"] = list(value)[:50]
            result["collection_lengths"] = {key: len(val) for key, val in value.items() if isinstance(val, list)}
        elif isinstance(value, list):
            result["length"] = len(value)
            if value and isinstance(value[0], dict):
                result["first_item_keys"] = list(value[0])[:50]
        return result
    if path.suffix.lower() == ".xml":
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError("DTD/entities are not permitted")
        root = ET.fromstring(text)
        return {"syntax": "xml", "root_tag": root.tag,
                "element_counts": dict(Counter(element.tag for element in root.iter()))}
    return {"syntax": "uninterpreted_text", "first_lines": text.splitlines()[:8],
            "note": "May be metadata, splits, class names or annotations; not yet classified"}


def inspect_dataset(root, sample_count=20):
    from PIL import Image

    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Dataset root must be a directory")
    files, skipped_links = [], []
    # Do not traverse symlinks or junctions outside the selected dataset.
    def walk(directory):
        for path in sorted(directory.iterdir()):
            if path.is_symlink() or path.is_junction():
                skipped_links.append(path.relative_to(root).as_posix())
            elif path.is_dir():
                walk(path)
            elif path.is_file():
                files.append(path)
    walk(root)
    images = [path for path in files if path.suffix.lower() in IMAGE_EXTENSIONS]
    candidates = [path for path in files if path.suffix.lower() in CANDIDATE_EXTENSIONS]
    resolutions, corrupt, valid_images = Counter(), [], []
    for path in images:
        try:
            with Image.open(path) as image:
                size = image.size
                image.verify()
            with Image.open(path) as image:
                image.load()  # verify() alone does not guarantee full pixel decoding
            resolutions[f"{size[0]}x{size[1]}"] += 1
            valid_images.append(path)
        except Exception as exc:
            corrupt.append({"path": path.relative_to(root).as_posix(),
                            "error": f"{type(exc).__name__}: {exc}"})
    probes = []
    # Spread review samples across extensions rather than showing only the first TXT files.
    selected = []
    groups = [[p for p in candidates if p.suffix.lower() == ext] for ext in sorted(CANDIDATE_EXTENSIONS)]
    for index in range(sample_count):
        for group in groups:
            if index < len(group) and len(selected) < sample_count:
                selected.append(group[index])
    for path in selected:
        probe = {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size}
        try:
            probe.update(annotation_probe(path))
        except (ValueError, UnicodeError, ET.ParseError) as exc:
            probe.update({"status": "syntax_error", "error": f"{type(exc).__name__}: {exc}"})
        probes.append(probe)
    report = {
        "stage": "inventory_only", "annotation_status": "requires_schema_confirmation",
        "dataset_root": str(root), "file_count": len(files),
        "extensions": dict(sorted(Counter(p.suffix.lower() for p in files).items())),
        "files": [p.relative_to(root).as_posix() for p in files],
        "image_count": len(images), "decoded_image_count": len(valid_images),
        "resolution_counts": dict(sorted(resolutions.items())), "corrupt_images": corrupt,
        "annotation_candidate_file_count": len(candidates),
        "annotation_probes": probes, "skipped_links": skipped_links,
        "annotation_count": None, "classes": None, "objects_per_class": None,
        "bbox_statistics": None, "missing_referenced_files": None,
        "invalid_annotations": None, "ground_truth_previews": [],
        "limitations": [
            "Candidate files are not confirmed annotations. Probes cover a bounded sample only.",
            "Class mapping, annotation counts, missing references and bbox statistics are unknown until schema review.",
            "No ground-truth previews or YOLO readiness claim before confirming coordinate and class conventions.",
            "Image counts use known extensions; inspect the full inventory for other image types.",
        ],
    }
    return report


def write_report(report, output):
    output = Path(output).absolute()
    root = Path(report["dataset_root"]).resolve()
    if output.resolve().is_relative_to(root) or root.is_relative_to(output.resolve()):
        raise ValueError("Report directory must be separate from the source dataset")
    output.mkdir(parents=True, exist_ok=False)
    try:
        commit = subprocess.run(["git", "-c", f"safe.directory={Path(__file__).resolve().parents[1].as_posix()}",
                                 "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=5, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = None
    manifest = {"git_sha": commit, "created_at": datetime.now(timezone.utc).isoformat(),
                "python": platform.python_version(), "stage": report["stage"],
                "script_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                  for name in ("inspect_dataset.py", "download_dataset.py", "check_env.py", "voc_dataset.py")},
                "dataset_revision": None, "note": "Record source archive SHA256 and revision alongside this report"}
    if "archive_provenance" in report:
        manifest["archive_provenance"] = report["archive_provenance"]
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "dataset_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Dataset feasibility: initial inventory", "", "**Status: annotation schema not confirmed.**", "",
             f"- Files: {report['file_count']}", f"- Images: {report['image_count']}",
             f"- Fully decoded images: {report['decoded_image_count']}",
             f"- Corrupt images: {len(report['corrupt_images'])}",
             f"- Candidate annotation/metadata files: {report['annotation_candidate_file_count']}",
             "", "## Resolutions", "", "```json", json.dumps(report["resolution_counts"], indent=2), "```",
             "", "## Not established", ""]
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend(["", "See dataset_report.json for complete paths, syntax probes and image errors.",
                  "", "Next: inspect real annotation samples, confirm class map and coordinate convention,",
                  "then implement and test the matching parser and produce 10–20 GT previews."])
    (output / "dataset_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="NEW directory outside dataset root")
    parser.add_argument("--samples", type=int, default=20, help="Number of syntax probes, 1–100")
    parser.add_argument("--format", choices=("inventory", "voc"), default="inventory",
                        help="Explicit VOC parser only after schema review; default remains inventory")
    parser.add_argument("--archive", type=Path, help="Optional source ZIP for SHA256 provenance (no download)")
    args = parser.parse_args()
    if not 1 <= args.samples <= 100:
        parser.error("--samples must be between 1 and 100")
    if args.output.exists():
        parser.error("--output must not already exist")
    report = inspect_dataset(args.root, args.samples)
    if args.format == "voc":
        from voc_dataset import audit_voc
        report = audit_voc(args.root, report)
    if args.archive:
        from download_dataset import inspect_archive
        report["archive_provenance"] = inspect_archive(args.archive)
    write_report(report, args.output)
    if args.format == "voc":
        from voc_dataset import generate_previews, write_voc_markdown
        generate_previews(args.root, report, args.output)
        (args.output / "dataset_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        write_voc_markdown(report, args.output)
    print(f"{report['stage']} report written to {args.output}")


if __name__ == "__main__":
    main()
