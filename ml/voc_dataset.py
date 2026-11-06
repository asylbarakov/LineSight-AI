"""Audit the VOC XML layout observed in the supplied transmission-line archive.

Derived coordinates are separate from immutable XML; zero-size canvases are quarantined.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import statistics
import xml.etree.ElementTree as ET


def parse_voc(path, data=None):
    data = Path(path).read_bytes() if data is None else data
    if len(data) > 1024 * 1024 or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Oversized XML or forbidden DTD/entity")
    root = ET.fromstring(data)
    if root.tag != "annotation":
        raise ValueError("Expected VOC annotation root")
    filename = root.findtext("filename", "").strip()
    if not filename or "/" in filename or "\\" in filename or PureWindowsPath(filename).drive or filename in (".", ".."):
        raise ValueError("Expected a plain image filename")
    width = float(root.findtext("size/width", "nan"))
    height = float(root.findtext("size/height", "nan"))
    if not all(math.isfinite(v) and v >= 0 for v in (width, height)):
        raise ValueError("Invalid XML size")
    objects = []
    for index, node in enumerate(root.findall("object")):
        obj = {"index": index, "class": node.findtext("name", ""),
               "difficult": node.findtext("difficult", "0"),
               "truncated": node.findtext("truncated", "0")}
        try:
            if not obj["class"].strip():
                raise ValueError("Missing class name")
            box = [float(node.findtext(f"bndbox/{key}", "nan")) for key in ("xmin", "ymin", "xmax", "ymax")]
            if not all(math.isfinite(v) for v in box):
                raise ValueError("Nonfinite/missing bbox")
            obj["raw_xyxy"] = box
        except ValueError as exc:
            obj["error"] = str(exc)
        objects.append(obj)
    return {"filename": filename, "xml_size": [width, height], "objects": objects}


def project_box(box, canvas, actual):
    width, height = canvas
    aw, ah = actual
    if width <= 0 or height <= 0:
        raise ValueError("Unknown coordinate canvas (zero XML size); do not guess")
    x1, y1, x2, y2 = box
    if not all(math.isfinite(v) for v in (*box, width, height, aw, ah)):
        raise ValueError("Nonfinite box or size")
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height and aw > 0 and ah > 0):
        raise ValueError("Box outside XML canvas, reversed or empty")
    if abs((width / height) / (aw / ah) - 1) > 0.02:
        raise ValueError("XML/image aspect ratio differs by more than 2%; projection ambiguous")
    return [x1 * aw / width, y1 * ah / height, x2 * aw / width, y2 * ah / height]


def distribution(values):
    values = sorted(values)
    if not values:
        return {"n": 0}
    def quantile(q):
        index = (len(values) - 1) * q
        low = int(index)
        return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (index - low)
    return {"n": len(values), "min": values[0], "p10": quantile(.1), "median": statistics.median(values),
            "p90": quantile(.9), "max": values[-1], "mean": statistics.mean(values)}


def resolve_image(folder, filename, image_lookup):
    """Exact local match, then reversible GBK/CP437 ZIP-name decoding only."""
    key = folder.as_posix().casefold()
    matches = image_lookup.get((key, filename.casefold()), [])
    if matches:
        return matches, "filename"
    try:
        legacy_name = filename.encode("gbk").decode("cp437")
    except UnicodeError:
        return [], "unresolved"
    matches = image_lookup.get((key, legacy_name.casefold()), [])
    return matches, "gbk_cp437_filename" if matches else "unresolved"


def box_statistics(objects):
    return {key: distribution([obj[key] for obj in objects]) for key in
            ("width_px", "height_px", "relative_width", "relative_height", "relative_area", "short_side_px")}


def audit_voc(root, inventory):
    from PIL import Image
    root = Path(root).resolve()
    files = [root / name for name in inventory["files"]]
    images = [p for p in files if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")]
    xmls = [p for p in files if p.suffix.lower() == ".xml"]
    image_lookup = defaultdict(list)
    actual_sizes, hashes = {}, defaultdict(list)
    corrupt = {item["path"] for item in inventory["corrupt_images"]}
    for path in images:
        rel = path.relative_to(root).as_posix()
        image_lookup[(path.parent.as_posix().casefold(), path.name.casefold())].append(path)
        if rel not in corrupt:
            with Image.open(path) as image:
                actual_sizes[rel] = list(image.size)
            hashes[hashlib.sha256(path.read_bytes()).hexdigest()].append(rel)
    raw_counts, valid_counts, raw_images, valid_images = Counter(), Counter(), defaultdict(set), defaultdict(set)
    invalid, warnings, missing, objects, records = [], [], [], [], []
    reference_issues, raw_image_sets = [], defaultdict(set)
    paired = set()
    scales = Counter()
    annotation_hasher = hashlib.sha256()
    zero_size_count = 0
    empty_annotations, object_histogram, difficult_flags = [], Counter(), Counter()
    for path in xmls:
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        annotation_hasher.update(rel.encode("utf-8") + b"\0" + hashlib.sha256(data).digest())
        try:
            record = parse_voc(path, data=data)
        except (ValueError, ET.ParseError) as exc:
            invalid.append({"annotation": rel, "reason": str(exc)})
            continue
        record["annotation"] = rel
        zero_size_count += min(record["xml_size"]) <= 0
        object_histogram[len(record["objects"])] += 1
        if not record["objects"]:
            empty_annotations.append(rel)
        difficult_flags.update(obj["difficult"] for obj in record["objects"])
        for obj in record["objects"]:
            raw_counts[obj["class"]] += 1
            raw_images[obj["class"]].add(rel)
        expected_folder = path.parent.parent / "JPEGImages"
        matches, pairing = resolve_image(expected_folder, record["filename"], image_lookup)
        if pairing != "filename":
            reference_issues.append({"annotation": rel, "filename": record["filename"], "pairing": pairing,
                                     "resolved_image": matches[0].relative_to(root).as_posix() if len(matches) == 1 else None})
        if len(matches) != 1:
            missing.append({"annotation": rel, "filename": record["filename"], "matches": len(matches)})
            continue
        image_rel = matches[0].relative_to(root).as_posix()
        paired.add(image_rel)
        record["image"] = image_rel
        record["pairing"] = pairing
        records.append(record)
        for obj in record["objects"]:
            raw_image_sets[obj["class"]].add(image_rel)
        if path.stem.casefold() != Path(record["filename"]).stem.casefold():
            warnings.append({"annotation": rel, "reason": "XML stem differs from filename"})
        if image_rel not in actual_sizes:
            invalid.append({"annotation": rel, "reason": "Paired image failed decoding"})
            continue
        actual = actual_sizes[image_rel]
        record["actual_size"] = actual
        canvas = record["xml_size"]
        if canvas != actual:
            warnings.append({"annotation": rel, "reason": "XML/image size mismatch", "xml_size": canvas, "actual_size": actual})
        if min(canvas) > 0:
            scales[f"{actual[0]/canvas[0]:.6f},{actual[1]/canvas[1]:.6f}"] += 1
        if min(canvas) <= 0:
            invalid.append({"annotation": rel, "reason": "Zero XML size; all boxes quarantined"})
        seen_boxes = set()
        for obj in record["objects"]:
            base = {"annotation": rel, "image": image_rel, "object_index": obj["index"], "class": obj["class"]}
            try:
                if "error" in obj:
                    raise ValueError(obj["error"])
                projected = project_box(obj["raw_xyxy"], canvas, actual)
                key = (obj["class"], *obj["raw_xyxy"])
                if key in seen_boxes:
                    warnings.append({**base, "reason": "Duplicate class/bbox within XML"})
                seen_boxes.add(key)
                x1, y1, x2, y2 = projected
                aw, ah = actual
                item = {**base, "raw_xyxy": obj["raw_xyxy"], "image_xyxy": projected,
                        "xml_size": canvas, "actual_size": actual,
                        "width_px": x2 - x1, "height_px": y2 - y1,
                        "short_side_px": min(x2-x1, y2-y1),
                        "relative_width": (x2-x1)/aw, "relative_height": (y2-y1)/ah,
                        "relative_area": (x2-x1)*(y2-y1)/(aw*ah)}
                objects.append(item)
                valid_counts[obj["class"]] += 1
                valid_images[obj["class"]].add(image_rel)
            except ValueError as exc:
                invalid.append({**base, "raw_xyxy": obj.get("raw_xyxy"), "reason": str(exc)})
    by_class = defaultdict(list)
    for obj in objects:
        by_class[obj["class"]].append(obj)
    duplicate_groups = [paths for paths in hashes.values() if len(paths) > 1]
    report = {**inventory, "stage": "voc_feasibility", "annotation_status": "voc_xml_parsed_with_quarantine",
              "annotation_count": len(xmls), "classes": sorted(raw_counts),
              "objects_per_class": dict(raw_counts.most_common()), "raw_object_count": sum(raw_counts.values()),
              "usable_objects_per_class": dict(valid_counts.most_common()), "usable_object_count": len(objects),
              "annotation_files_per_class": {key: len(raw_images[key]) for key in sorted(raw_images)},
              "images_per_class": {key: len(raw_image_sets[key]) for key in sorted(raw_images)},
              "usable_images_per_class": {key: len(valid_images[key]) for key in sorted(raw_images)},
              "bbox_statistics": box_statistics(objects),
              "bbox_statistics_per_class": {key: box_statistics(value) for key, value in by_class.items()},
              "small_object_counts": {f"short_side_lt_{limit}px": sum(o["short_side_px"] < limit for o in objects) for limit in (8, 16, 32)},
              "relative_area_histogram": {
                  "lt_0.1_percent": sum(o["relative_area"] < .001 for o in objects),
                  "0.1_to_1_percent": sum(.001 <= o["relative_area"] < .01 for o in objects),
                  "1_to_10_percent": sum(.01 <= o["relative_area"] < .1 for o in objects),
                  "gte_10_percent": sum(o["relative_area"] >= .1 for o in objects)},
              "missing_referenced_files": missing, "images_without_xml": sorted(set(actual_sizes) - paired),
              "filename_reference_issues": reference_issues,
              "invalid_annotations": invalid, "annotation_warnings": warnings,
              "xml_to_image_scale_counts": dict(scales.most_common()),
              "exact_duplicate_image_groups": duplicate_groups, "objects": objects,
              "coordinate_policy": "Raw pixel xmin,ymin,xmax,ymax on XML size; derived image boxes scale by actual/XML. No clipping. Zero-size canvas or aspect discrepancy >2% quarantined. Pixel origin/inclusivity not documented; no +/-1 applied.",
              "limitations": [
                  "Rescaling assumes images preserve the XML field of view; GT previews require visual review.",
                  "Usable means structurally valid under the stated projection, not semantically verified training labels.",
                  "Unannotated images are not verified negatives. Do not treat them as background automatically.",
                  "Exact duplicate groups must stay within the same split; near-duplicate/scene leakage remains untested.",
                  "Raw class strings are preserved; alias/typo merging requires agreement.",
                  "Legacy ZIP filename encoding is resolved only by a reversible GBK/CP437 match; PNG/JPG changes are not guessed.",
                  "No detection metrics or proof of drone-video performance; source annotations remain unchanged.",
              ]}
    report["sidecar_txt"] = inspect_sidecars(root, files, records)
    report["invalid_reason_counts"] = dict(Counter(item["reason"] for item in invalid))
    report["invalid_annotation_file_count"] = len({item["annotation"] for item in invalid})
    report["zero_size_xml_file_count"] = zero_size_count
    report["source_annotation_sha256"] = annotation_hasher.hexdigest()
    report["empty_annotations"] = empty_annotations
    report["objects_per_annotation_histogram"] = dict(object_histogram)
    report["difficult_flag_counts"] = dict(difficult_flags)
    enrich_quality(report)
    return report


def enrich_quality(report):
    labels = defaultdict(set)
    for obj in report["objects"]:
        labels[obj["image"]].add(obj["class"])
    differing = [group for group in report["exact_duplicate_image_groups"]
                 if len({tuple(sorted(labels[path])) for path in group}) > 1]
    report["duplicate_groups_with_different_projectable_labels"] = differing
    invalid_files = {item["annotation"] for item in report["invalid_annotations"]}
    candidate_images = {obj["image"] for obj in report["objects"]}
    unsafe_images = {obj["image"] for obj in report["objects"] if obj["annotation"] in invalid_files}
    report["fully_projectable_nonempty_image_count"] = len(candidate_images - unsafe_images)
    report["training_cautions"] = [
        "Projectable object counts are geometry checks, not an approved training set.",
        "Quarantine entire images containing invalid/uncertain objects, not just those boxes, to avoid false-negative labels.",
        "Review duplicate-image groups with differing labels; some are incomplete, ambiguous or unpaired annotations rather than proven class errors.",
        "Group exact and near duplicates and related scenes before making train/validation/test splits.",
        "The source contains close-up distribution-line infrastructure; transfer to distant drone footage/high-voltage lines is unverified.",
    ]


def inspect_sidecars(root, files, records):
    results = []
    for path in files:
        if path.suffix.lower() != ".txt":
            continue
        text = path.read_text(encoding="utf-8-sig")
        item = {"path": path.relative_to(root).as_posix(), "text": text}
        if path.name.lower() != "classes.txt":
            class_path = path.with_name("classes.txt")
            names = [line.strip() for line in class_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()] if class_path.exists() else []
            item["local_classes"] = names
            matching = [record for record in records if record["annotation"] == path.with_suffix(".xml").relative_to(root).as_posix()]
            comparisons = []
            for line in text.splitlines():
                if not line.strip():
                    continue
                try:
                    tokens = line.split()
                    if len(tokens) != 5:
                        raise ValueError("Expected class_id cx cy w h")
                    cid = int(tokens[0])
                    cx, cy, w, h = map(float, tokens[1:])
                    if not 0 <= cid < len(names) or not all(math.isfinite(v) and 0 <= v <= 1 for v in (cx,cy,w,h)) or w <= 0 or h <= 0:
                        raise ValueError("Invalid normalized row")
                    entry = {"class": names[cid], "normalized_xyxy": [cx-w/2,cy-h/2,cx+w/2,cy+h/2]}
                    distances = []
                    for record in matching:
                        iw, ih = record["xml_size"]
                        if min(iw,ih) <= 0:
                            continue
                        for obj in record["objects"]:
                            if obj["class"] == names[cid] and "raw_xyxy" in obj:
                                normalized = [v/d for v,d in zip(obj["raw_xyxy"], (iw,ih,iw,ih))]
                                distances.append(max(abs(a-b) for a,b in zip(normalized,entry["normalized_xyxy"])))
                    entry["nearest_xml_max_abs_delta"] = min(distances) if distances else None
                    comparisons.append(entry)
                except ValueError as exc:
                    comparisons.append({"error": str(exc), "line": line})
            item["comparisons"] = comparisons
            item["xml_classes"] = sorted({obj["class"] for record in matching for obj in record["objects"]})
            item["class_conflict_with_xml"] = any(entry.get("class") not in item["xml_classes"] for entry in comparisons if "class" in entry)
            item["policy"] = "Diagnostic only; XML is counted once, TXT sidecars never added to object totals"
        results.append(item)
    return results


def generate_previews(root, report, output, count=18):
    from PIL import Image, ImageDraw
    directory = Path(output) / "previews"
    directory.mkdir()
    groups = defaultdict(list)
    image_objects = defaultdict(list)
    for obj in report["objects"]:
        groups[obj["class"]].append(obj)
        image_objects[obj["image"]].append(obj)
    # Top classes plus bird nests if projectable; three size strata per class.
    classes = [name for name in ("czjyz_ps", "czjyz_lw", "czjyz_sl", "dx_jypps", "dx_dg", "nw") if groups[name]]
    classes += [name for name in report["usable_objects_per_class"] if name not in classes]
    selected, used = [], set()
    for name in classes:
        values = sorted(groups[name], key=lambda o: (o["relative_area"], o["image"]))
        for fraction in (.1, .5, .9):
            start = int((len(values)-1)*fraction)
            choices = sorted(range(len(values)), key=lambda i: abs(i-start))
            obj = next((values[i] for i in choices if values[i]["image"] not in used), None)
            if obj is not None:
                selected.append(obj)
                used.add(obj["image"])
            if len(selected) >= count:
                break
        if len(selected) >= count:
            break
    thumbnails, manifest = [], []
    for index, chosen in enumerate(selected, 1):
        with Image.open(Path(root) / chosen["image"]) as source:
            image = source.convert("RGB")
        draw = ImageDraw.Draw(image)
        for obj in image_objects[chosen["image"]]:
            box = obj["image_xyxy"]
            draw.rectangle(box, outline="#00ff70", width=2)
            draw.text((box[0], max(0,box[1]-12)), obj["class"], fill="#ff3030", stroke_width=1, stroke_fill="white")
        filename = f"{index:02d}_{chosen['class']}.jpg"
        image.save(directory / filename, quality=92)
        thumb = image.copy()
        thumb.thumbnail((320, 230))
        tile = Image.new("RGB", (320, 270), "white")
        tile.paste(thumb, ((320-thumb.width)//2, 30))
        ImageDraw.Draw(tile).text((4,4), f"{index:02d} {chosen['class']} area={chosen['relative_area']:.4f}", fill="black")
        thumbnails.append(tile)
        manifest.append({"preview": f"previews/{filename}", "selected_for": chosen["class"],
                         "selected_relative_area": chosen["relative_area"], "image": chosen["image"],
                         "annotation": chosen["annotation"], "xml_size": chosen["xml_size"],
                         "actual_size": chosen["actual_size"]})
    sheet = Image.new("RGB", (960, 270 * math.ceil(len(thumbnails)/3)), "#dddddd")
    for index, tile in enumerate(thumbnails):
        sheet.paste(tile, ((index%3)*320, (index//3)*270))
    if thumbnails:
        sheet.save(Path(output) / "gt_contact_sheet.jpg", quality=90)
    report["ground_truth_previews"] = manifest
    (Path(output) / "preview_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def write_voc_markdown(report, output):
    lines = ["# Power Equipment Image Dataset — Dataset Feasibility", "",
             "Source: user-supplied transmission line object detection.zip. No training performed.", "",
             f"Images: {report['image_count']}; XML: {report['annotation_count']}; raw objects: {report['raw_object_count']}; classes: {len(report['classes'])}.",
             f"Structurally projectable objects: {report['usable_object_count']}. Corrupt images: {len(report['corrupt_images'])}.",
             f"Unmatched XML references: {len(report['missing_referenced_files'])}; decoded images without XML: {len(report['images_without_xml'])}.",
             f"Invalid annotation/object records: {len(report['invalid_annotations'])}; warnings: {len(report['annotation_warnings'])}.", "",
             f"Zero-size XML (including unpaired files): {report['zero_size_xml_file_count']}. Invalid annotation files: {report['invalid_annotation_file_count']}.",
             f"Filename reference issues: {len(report['filename_reference_issues'])}; reversible GBK/CP437 matches: {sum(x['pairing']=='gbk_cp437_filename' for x in report['filename_reference_issues'])}.", "",
             f"Empty XML annotations: {len(report['empty_annotations'])}; these are not automatically trusted negative examples.", "",
             "## Coordinate policy", "", report["coordinate_policy"], "",
             "## Classes (original strings, no alias merging)", "",
             "| Class | Raw objects | Projectable objects | Images | Projectable images |",
             "|---|---:|---:|---:|---:|"]
    for name, number in report["objects_per_class"].items():
        lines.append(f"| `{name}` | {number} | {report['usable_objects_per_class'].get(name,0)} | {report['images_per_class'][name]} | {report['usable_images_per_class'][name]} |")
    lines += ["", "## Bbox distributions on actual JPEG pixels", "", "```json", json.dumps(report["bbox_statistics"], indent=2), "```",
              "", "Relative area bins:", "", "```json", json.dumps(report["relative_area_histogram"], indent=2), "```",
              "", "## Resolution distribution", "", "```json", json.dumps(report["resolution_counts"], indent=2), "```",
              "", "## Scale factors actual/XML", "", "```json", json.dumps(report["xml_to_image_scale_counts"], indent=2), "```",
              "", "## Quality and split risks", ""]
    lines += [f"- {item}" for item in report["limitations"]]
    lines += [f"- {item}" for item in report["training_cautions"]]
    lines += [f"- Exact duplicate image groups: {len(report['exact_duplicate_image_groups'])}.",
              f"- Duplicate groups with different projectable label sets: {len(report['duplicate_groups_with_different_projectable_labels'])} (review candidates, not proven semantic errors).",
              f"- Fully projectable nonempty images before deduplication/semantic review: {report['fully_projectable_nonempty_image_count']}.",
              "- Full file/error lists, raw/derived boxes and TXT sidecar comparisons are in dataset_report.json.",
              "- TXT sidecars are diagnostics only and do not duplicate XML object counts.", "",
              "## Candidate experiment", "",
              "Start with czjyz_ps (porcelain post insulator damage): largest class, visible chipped ceramic in reviewed previews.",
              "Optional second class: nw (bird nest), visually distinct on overhead structures but with fewer examples and broad scale variation.",
              "Optional third class: dx_dg (conductor strand breakage); review small/ambiguous cases before inclusion.",
              "Postpone czjyz_lw (crack) and czjyz_sl (flashover) until a semantic review: hairline cracks and discoloration are difficult at this JPEG resolution.",
              "Class descriptions: https://huggingface.co/datasets/sxiong/Power-equipment-image-dataset/blob/main/README.md",
              "Before YOLO: quarantine uncertain/invalid boxes; agree aliases; deduplicate/group scenes before splitting; inspect label completeness and negative examples.",
              "No YOLO labels are exported and no source files are modified in this iteration.", "",
              "## GT preview review", "", "18 previews target different classes and relative-area strata; see preview_manifest.json.",
              "![GT contact sheet](gt_contact_sheet.jpg)", ""]
    (Path(output) / "dataset_report.md").write_text("\n".join(lines), encoding="utf-8")
