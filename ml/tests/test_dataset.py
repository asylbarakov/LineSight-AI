"""CPU-only safety and inventory checks; no GPU, network or real dataset."""
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
from types import ModuleType
import zipfile

import pytest


def load_script(name):
    path = Path(__file__).resolve().parents[1] / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"feasibility_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


download = load_script("download_dataset")
inspect = load_script("inspect_dataset")
voc = load_script("voc_dataset")


@pytest.fixture(autouse=True)
def synthetic_archive_disk_budget(monkeypatch):
    # Tiny fixtures test archive logic independently of the host's free space.
    # The dedicated low-space test overrides this mock explicitly.
    from types import SimpleNamespace
    monkeypatch.setattr(download.shutil, "disk_usage", lambda _: SimpleNamespace(free=10 * 1024**3))


@pytest.mark.parametrize("name", ["../escape.txt", "/absolute.txt", "C:/escape.txt", "a\\escape.txt",
                                  "a/../../escape.txt", "CON.txt", "a./x", "a:stream", "a//x"])
def test_reject_unsafe_archive_names(tmp_path, name):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as target:
        info = zipfile.ZipInfo("placeholder")
        info.filename = name  # Preserve adversarial spelling on Windows too.
        info.orig_filename = name
        target.writestr(info, "data")
    with pytest.raises(ValueError):
        download.safe_extract(archive, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".extract-*"))


def test_extract_and_refuse_overwrite(tmp_path):
    archive = tmp_path / "data.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("images/a.txt", "original")
    result = download.safe_extract(archive, tmp_path / "out")
    assert (result / "images/a.txt").read_text() == "original"
    assert download.inspect_archive(archive)["entries"] == 1
    with pytest.raises(FileExistsError):
        download.safe_extract(archive, result)


def test_file_directory_conflict_cleans_staging(tmp_path):
    archive = tmp_path / "conflict.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("file", "data")
        target.writestr("file/child", "data")
    with pytest.raises(OSError):
        download.safe_extract(archive, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".extract-*"))


def test_download_is_explicit_and_targets_one_file(tmp_path, monkeypatch, capsys):
    archive = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("fixture.txt", "synthetic")
    calls = []
    hub = ModuleType("huggingface_hub")
    def fake_download(**kwargs):
        calls.append(kwargs)
        return str(archive)
    hub.hf_hub_download = fake_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setattr(sys, "argv", ["download_dataset.py", "--archive", str(archive)])
    download.main()
    assert calls == []
    capsys.readouterr()
    monkeypatch.setattr(sys, "argv", ["download_dataset.py", "--download", "--revision", "fixture-sha"])
    download.main()
    assert len(calls) == 1
    assert calls[0]["repo_id"] == "sxiong/Power-equipment-image-dataset"
    assert calls[0]["repo_type"] == "dataset"
    assert calls[0]["filename"] == "transmission line object detection.zip"
    assert calls[0]["revision"] == "fixture-sha"
    assert json.loads(capsys.readouterr().out)["sha256"] == download.sha256_file(archive)


def test_cli_requires_explicit_source_and_revision(monkeypatch):
    for argv in (["download_dataset.py"], ["download_dataset.py", "--download"]):
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as exc:
            download.main()
        assert exc.value.code == 2


def test_reject_symlink_collision_and_size_limit(tmp_path):
    for case in ("symlink", "collision", "size"):
        archive = tmp_path / f"{case}.zip"
        with zipfile.ZipFile(archive, "w") as target:
            if case == "symlink":
                info = zipfile.ZipInfo("link")
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                target.writestr(info, "../outside")
            elif case == "collision":
                target.writestr("A.txt", "a")
                target.writestr("a.txt", "b")
            else:
                target.writestr("large.txt", "1234")
        with pytest.raises(ValueError):
            download.safe_extract(archive, tmp_path / case, max_bytes=3 if case == "size" else 1000)


@pytest.mark.parametrize("box", [(1, 1, 0, 2), (-1, 0, 5, 5), (0, 0, 101, 10),
                                 (0, 0, float("nan"), 10), (0, 0, 0, 10)])
def test_invalid_explicit_bbox(box):
    with pytest.raises(ValueError):
        inspect.validate_bbox(box, 100, 50)


def test_bbox_relative_size():
    assert inspect.validate_bbox((10, 5, 30, 15), 100, 50) == {
        "width_px": 20, "height_px": 10, "relative_width": 0.2,
        "relative_height": 0.2, "relative_area": 0.04,
    }


def test_syntax_probes_and_no_schema_guess(tmp_path):
    (tmp_path / "sample.xml").write_text("<annotation><object><name>fixture</name></object></annotation>")
    assert inspect.annotation_probe(tmp_path / "sample.xml")["element_counts"]["object"] == 1
    (tmp_path / "sample.json").write_text('{"images": [], "annotations": []}')
    assert inspect.annotation_probe(tmp_path / "sample.json")["top_level_keys"] == ["images", "annotations"]
    (tmp_path / "sample.txt").write_text("0 0.5 0.5 0.1 0.1")
    assert inspect.annotation_probe(tmp_path / "sample.txt")["syntax"] == "uninterpreted_text"
    (tmp_path / "entity.xml").write_text('<!DOCTYPE x [<!ENTITY e "bad">]><x>&e;</x>')
    with pytest.raises(ValueError):
        inspect.annotation_probe(tmp_path / "entity.xml")


def test_inventory_reports_real_counts_without_fake_gt(tmp_path):
    image_module = pytest.importorskip("PIL.Image")
    root = tmp_path / "dataset"
    root.mkdir()
    image_module.new("RGB", (80, 40)).save(root / "valid.png")
    (root / "broken.jpg").write_bytes(b"not an image")
    (root / "label.txt").write_text("unknown annotation syntax")
    (root / "broken.json").write_text("{")
    report = inspect.inspect_dataset(root)
    assert report["image_count"] == 2
    assert report["decoded_image_count"] == 1
    assert report["resolution_counts"] == {"80x40": 1}
    assert report["corrupt_images"][0]["path"] == "broken.jpg"
    assert report["annotation_candidate_file_count"] == 2
    assert report["classes"] is None and report["annotation_count"] is None
    assert report["ground_truth_previews"] == []
    assert any(p.get("status") == "syntax_error" for p in report["annotation_probes"])
    output = tmp_path / "report"
    inspect.write_report(report, output)
    assert json.loads((output / "dataset_report.json").read_text())["image_count"] == 2
    with pytest.raises(FileExistsError):
        inspect.write_report(report, output)
    with pytest.raises(ValueError):
        inspect.write_report(report, root / "reports")
    assert (root / "label.txt").read_text() == "unknown annotation syntax"


def test_inventory_cli_on_synthetic_directory(tmp_path):
    pytest.importorskip("PIL.Image")
    root = tmp_path / "synthetic-data"
    root.mkdir()
    (root / "labels.txt").write_text("format is intentionally unknown")
    output = tmp_path / "cli-report"
    script = Path(inspect.__file__)
    result = subprocess.run([sys.executable, str(script), str(root), "--output", str(output)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads((output / "dataset_report.json").read_text())
    assert report["stage"] == "inventory_only"
    assert report["classes"] is None


def test_voc_projection_uses_xml_canvas_not_image_canvas():
    assert voc.project_box([1379, 608, 1624, 754], [3264, 2448], [816, 612]) == [344.75, 152, 406, 188.5]
    for canvas, actual, box in (([0, 0], [100, 100], [1, 1, 10, 10]),
                                ([200, 100], [100, 100], [1, 1, 10, 10]),
                                ([100, 100], [100, 100], [0, 0, 101, 10])):
        with pytest.raises(ValueError):
            voc.project_box(box, canvas, actual)


def test_voc_parser_preserves_raw_class_and_flags_malformed_box(tmp_path):
    xml = tmp_path / "fixture.xml"
    xml.write_text('<annotation><filename>a.jpg</filename><size><width>100</width><height>50</height></size>'
                   '<object><name>dx_ jypps</name><bndbox><xmin>1</xmin><ymin>2</ymin><xmax>20</xmax><ymax>30</ymax></bndbox></object>'
                   '<object><name>broken</name></object></annotation>')
    parsed = voc.parse_voc(xml)
    assert parsed["objects"][0]["class"] == "dx_ jypps"
    assert parsed["objects"][0]["raw_xyxy"] == [1, 2, 20, 30]
    assert "error" in parsed["objects"][1]
    xml.write_text('<annotation><filename>../outside.jpg</filename></annotation>')
    with pytest.raises(ValueError):
        voc.parse_voc(xml)


def test_voc_audit_quarantines_zero_sizes_and_preserves_sources(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    root = tmp_path / "dataset"
    annotations = root / "group/Annotations"
    images = root / "group/JPEGImages"
    annotations.mkdir(parents=True)
    images.mkdir()
    template = ('<annotation><filename>{name}.jpg</filename><size><width>{width}</width><height>{height}</height></size>'
                '<object><name>fixture</name><bndbox><xmin>20</xmin><ymin>10</ymin><xmax>60</xmax><ymax>30</ymax></bndbox></object></annotation>')
    for name, width, height in (("good", 200, 100), ("zero", 0, 0), ("missing", 200, 100)):
        (annotations / f"{name}.xml").write_text(template.format(name=name, width=width, height=height))
        if name != "missing":
            Image.new("RGB", (100, 50)).save(images / f"{name}.jpg")
    Image.new("RGB", (100, 50)).save(images / "unlabelled.jpg")
    original = {p: p.read_bytes() for p in annotations.iterdir()}
    report = voc.audit_voc(root, inspect.inspect_dataset(root))
    assert report["annotation_count"] == 3
    assert report["objects_per_class"] == {"fixture": 3}
    assert report["usable_objects_per_class"] == {"fixture": 1}
    assert report["objects"][0]["image_xyxy"] == [10, 5, 30, 15]
    assert len(report["missing_referenced_files"]) == 1
    assert len(report["images_without_xml"]) == 1
    assert any("Zero XML size" in item["reason"] for item in report["invalid_annotations"])
    assert all(path.read_bytes() == data for path, data in original.items())
    output = tmp_path / "report"
    output.mkdir()
    voc.generate_previews(root, report, output, count=1)
    assert len(report["ground_truth_previews"]) == 1
    assert (output / "gt_contact_sheet.jpg").exists()


def test_extract_checks_free_space(tmp_path, monkeypatch):
    archive = tmp_path / "data.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("file", "data")
    from types import SimpleNamespace
    monkeypatch.setattr(download.shutil, "disk_usage", lambda _: SimpleNamespace(free=1))
    with pytest.raises(OSError, match="Insufficient free disk space"):
        download.safe_extract(archive, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_voc_legacy_zip_names_are_reversible_and_extensions_not_guessed(tmp_path):
    from collections import defaultdict
    lookup = defaultdict(list)
    name = "图片3.jpg"
    legacy = name.encode("gbk").decode("cp437")
    lookup[(tmp_path.as_posix().casefold(), legacy.casefold())].append(tmp_path / legacy)
    matches, strategy = voc.resolve_image(tmp_path, name, lookup)
    assert matches == [tmp_path / legacy]
    assert strategy == "gbk_cp437_filename"
    assert voc.resolve_image(tmp_path, "图片3.png", lookup)[0] == []


def test_quality_flags_duplicate_labels_and_quarantines_whole_image():
    report = {"objects": [
        {"image": "a.jpg", "class": "first", "annotation": "a.xml"},
        {"image": "b.jpg", "class": "second", "annotation": "b.xml"}],
        "exact_duplicate_image_groups": [["a.jpg", "b.jpg"]],
        "invalid_annotations": [{"annotation": "a.xml", "reason": "another invalid object"}]}
    voc.enrich_quality(report)
    assert report["duplicate_groups_with_different_projectable_labels"] == [["a.jpg", "b.jpg"]]
    assert report["fully_projectable_nonempty_image_count"] == 1
