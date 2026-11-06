# Dataset Feasibility — CPU, Windows / Conda

**Baseline preservation (7 November 2026):** the first YOLO11n Colab run is
complete. See [the versioned results summary](reports/baseline640_v1.md) and
[artifact SHA256/backup receipt](reports/baseline640_v1_artifacts.json).
The preparation instructions below describe the original workflow; statements
that the first Colab execution is pending reflect that earlier preparation stage.
Large artifacts remain ignored. An independent/Google Drive backup is unverified.

Current stage: **inventory and an explicit VOC audit** for the user-supplied real
archive. Default mode remains format-neutral inventory; `--format voc` opts into
the reviewed layout. Nothing from
`origin/asyl_experiment` has been copied. Worker, backend, Docker and CI are unchanged.

Use an existing Python **3.12+** Conda environment. Run commands from the repository
root. No CUDA, PyTorch, OpenCV or Ultralytics installation is needed. Image checking
uses Pillow; tests use pytest. `huggingface_hub` is optional until a download is
explicitly requested. `requirements-feasibility.txt` describes dependencies separately
from the worker; check existing packages before installing anything. Installing
dependencies or fetching the real dataset is a separate agreed action.

## Environment and tests

```powershell
conda activate <your-environment>
python ml/check_env.py
python -m pytest -q ml/tests/test_dataset.py
```

On this machine Anaconda base was found at
`C:\Users\danii\anaconda3\python.exe`; it has Pillow and pytest. The Python executable
on PATH is a different installation. Missing torch is reported normally, with
`cuda_available: false`; an unavailable/broken torch installation is not a GPU claim.

## Existing archive: inspect first, extraction is optional

Put the archive under ignored `ml/data/`, or use an external archive path.
The following commands do not use the network:

```powershell
python ml/download_dataset.py --archive "ml/data/transmission line object detection.zip"
python ml/download_dataset.py --archive "ml/data/transmission line object detection.zip" --extract-to ml/data/transmission-v1
```

The first command prints the SHA256, compressed/uncompressed sizes, extension counts
and first 50 paths. Extraction requires a **new** destination, rejects traversal,
absolute/Windows-special paths, links, encrypted files and case collisions, and
checks ZIP CRC while reading. Default limits: 100,000 entries and 4 GiB uncompressed.
Do not raise these limits without reviewing the archive. A failed extraction removes
its own staging directory. It never merges into an existing project directory.

## Optional download (unnecessary when the archive is already present)

```powershell
python ml/download_dataset.py --download --revision <dataset-commit-SHA>
```

Only `transmission line object detection.zip` from
`sxiong/Power-equipment-image-dataset` is requested. No repository snapshot or
20+ GiB download. `--revision main` is permitted explicitly but a commit SHA is
preferred. The returned archive path, SHA256 and requested revision must be retained
with the experiment. HF cache defaults to ignored `ml/data/hf-cache/`.
Importing modules, running `--help`, environment checks and local-archive commands
never trigger downloads. No token is accepted on the command line or written to logs.

## Inspect extracted files

```powershell
python ml/inspect_dataset.py ml/data/transmission-v1 --output ml/runs/inventory-001
```

The output directory must be **new** and separate from the source dataset. Outputs:

- `dataset_report.json`: complete file inventory and extension counts, image counts,
  resolution histogram, decoding failures, bounded XML/JSON/text syntax probes.
- `dataset_report.md`: compact human-readable status and remaining checks.
- `manifest.json`: Git HEAD, script SHA256 hashes, time, Python version and explicit
  provenance limitations.

All recognized images are fully decoded on CPU. Links/junctions are skipped. Annotation
probes default to 20 candidate files across extensions (`--samples 1..100`). Files over
1 MiB are listed but not parsed; XML DTD/entities are rejected. Candidate files may be
annotations, split lists, metadata or documentation. Text snippets are evidence only;
a five-number TXT row is **not** automatically classified as YOLO. Source files remain
unchanged. Use new run IDs, not overwriting previous reports.

## Reviewed real archive: VOC audit

```powershell
python ml/inspect_dataset.py ml/data/transmission-v1 --format voc --archive "ml/data/transmission line object detection.zip" --output ml/runs/power-equipment-voc-002
```

`voc_dataset.py` handles the observed `*/Annotations/*.xml` and sibling
`JPEGImages/` layout. XML stores pixel `xmin,ymin,xmax,ymax`; many XML sizes differ
from the distributed JPEG sizes. Raw coordinates are preserved. Derived preview
boxes use `actual_width/xml_width` and `actual_height/xml_height`. Zero-size XML
canvases, out-of-bounds/reversed boxes, and >2% aspect-ratio discrepancies are
quarantined, never silently repaired. Projection assumes the same field of view;
review previews before converting any labels for training. Pixel origin/inclusivity
is undocumented; no +/-1 convention is invented here.

VOC reports include raw and projectable object/image counts per exact class string,
bbox size quantiles in actual pixels and relative units, orphan files, errors,
size mismatches, exact duplicate-image groups and comparisons of the two TXT
sidecars against their XML (without double counting). `previews/` contains up to
18 GT overlays selected across classes and relative-size strata;
`gt_contact_sheet.jpg` and `preview_manifest.json` index them.

For this ZIP, 49 filename references have reversible GBK/CP437 encoding differences.
The parser matches those names without renaming any source file; extension changes
are never guessed. Reports distinguish these resolved references from missing files.
`duplicate_groups_with_different_projectable_labels` flags exact-image duplicates
requiring label review. Images containing any invalid objects must be quarantined
as a whole before training, even if their other boxes are geometrically projectable.

Completed local audit: `ml/runs/power-equipment-voc-003/` (ignored).
It includes `environment.json`, original annotation examples in `annotation_samples/`
and `source_integrity.json` comparing every XML byte-for-byte with the supplied ZIP.
The supplied archive was moved to `ml/data/transmission line object detection.zip`.
Its HF revision is unknown; SHA256 identifies the actual local data. No download or
package installation was necessary. Initial reports 001/002 are retained as audit
history; use 003 for the corrected filename pairing and final quality findings.

Unknown aliases are not merged. Unlabelled images are not verified negatives.
Semantic label correctness, near-duplicate/scene splitting, and drone-video domain
transfer still require review. The default inventory mode continues to leave
class/bbox fields unknown. The separate one-class v1 export is described below.

`ml/data/`, `ml/runs/` and `ml/.cache/` are ignored by Git. Keep archive provenance
and reports together under `ml/runs/`; share them locally for the next review.
The current manifest records HEAD but uncommitted scripts are not reproducible from
that SHA alone: preserve the reviewed code diff until a dedicated commit is made.
Dataset directories under the repository can enter Docker build context despite Git
ignores; no Docker configuration is changed here, so do not build containers with
large local datasets present (or keep the data outside the repository).

Existing worker tests use backend dependencies and `PYTHONPATH=backend;ml` on Windows.
The new tests use no database/network/GPU; the image fixture test skips clearly when
Pillow is absent, leaving worker CI dependency installation unchanged. This inventory
does not evaluate detection accuracy, mAP, real drone video or model training.

## YOLO Dataset v1 — local ceramic damage (`czjyz_ps`)

Completed set: `ml/data/yolo-czjyz-ps-v1/` (ignored). Train/val/test:
3,109 / 389 / 389 images; 3,259 / 405 / 412 boxes. It contains positive images only,
not verified negatives. JPEGs are hard links: **do not edit them in place**.
The target is the local damaged ceramic region, not the whole insulator.

Read `ml/runs/czjyz-ps-audit-v1/dataset_v1_report.md` and `semantic_audit.md`.
The audit covers 48 images (24 size-stratified, 8 random, 16 conflicting duplicates).
Decisions are retained in `ml/configs/czjyz_ps_review_v1.json`. All uncertain/excluded
cases propagate to their duplicate/near-duplicate groups. Other candidate images
were not individually semantically verified.

Exact SHA256, perceptual pHash/dHash pairs and named source batches define split
groups. This heuristic cannot prove that every adjacent view is discovered.
The plan records per-image exclusions, original XML paths, source hashes, class 0
labels and source annotation issues. No source VOC file is modified.

```powershell
python ml/prepare_yolo.py validate --dataset ml/data/yolo-czjyz-ps-v1
python -m pytest -q ml/tests/test_dataset.py ml/tests/test_yolo_dataset.py
```

To reproduce into a **new** directory from the frozen plan:

```powershell
python ml/prepare_yolo.py export --plan ml/runs/czjyz-ps-audit-v1/dataset_plan.json --source ml/data/transmission-v1 --output ml/data/yolo-czjyz-ps-v1-replay --hardlink
```

`--hardlink` requires source/output on the same filesystem. Omit it for ordinary
copies when enough space is available. YAML is generated with the actual absolute
dataset root; do not copy the local YAML unchanged to Colab.

Colab notebook: `ml/notebooks/colab_dataset_v1.ipynb`. Open it in a fresh CPU VM,
upload `ml/runs/czjyz-ps-audit-v1/colab_dataset_v1_bundle.zip`, then upload the
original archive or select the addressed HF download mode. The notebook checks
bundle/archive hashes, calls the same export/validation scripts and offers a small
receipt ZIP for download. It contains no training or inference calls.
The frozen bundle ships the reviewed uncommitted scripts without a GitHub push.
Colab UI execution has not yet been verified; local frozen-bundle replay is tested.

The dataset and bundle are versioned by their manifests/hashes. Changing source
scripts or split policy requires a new plan/bundle and updating the notebook's
expected bundle SHA256. Training on T4 is a later separately agreed step.

## First manual training baseline — YOLO11n / 640 / 25 epochs

Training is now prepared in the existing `ml/train.py` (previously empty).
It imports torch/Ultralytics only for the explicit `run` subcommand. No local
training or local GPU dependency installation was performed. Dataset v1 stays
frozen; the trainer sees a separate train/val view with copied labels, so label
cache writes cannot modify the source dataset. Test is omitted from that view/YAML.

- Config: `ml/configs/baseline_czjyz_ps_v1.json`.
- Colab-only dependency: `ml/requirements-colab.txt` (`ultralytics==8.3.228`).
- Notebook: `ml/notebooks/colab_baseline_v1.ipynb`.
- Upload bundle: `ml/runs/czjyz-ps-audit-v1/colab_baseline_v1_bundle.zip`.

YOLO11n is a COCO-pretrained one-stage nano detector. Defaults: imgsz 640, 25 epochs,
seed 20261103, deterministic mode, AdamW with lr0 0.001, AMP. Batch is 16 when free
VRAM is at least 14 GiB, otherwise 8 (at least 6 GiB required). Actual GPU/VRAM are
recorded; CUDA absence stops the runner rather than silently using CPU.
This initial policy is not an assurance against OOM. Config tuning never uses test.

Ultralytics is pinned; the runtime's compatible torch/torchvision/CUDA are reused.
The actual versions are captured by environment.json, pip-freeze.txt and nvidia-smi.txt.
No claim that the fresh Colab image is fully pinned before it is inspected.

### Exact first Colab launch

1. Open Google Colab and upload `ml/notebooks/colab_baseline_v1.ipynb`.
2. Select **Runtime → Change runtime type → T4 GPU**, then Save. Start with a fresh
   runtime; do not switch runtime type after preparing data, as /content may reset.
3. Run the bundle upload cell. Select **colab_baseline_v1_bundle.zip**, not the older
   preparation-only bundle. Its expected SHA256 is embedded in the notebook. Scripts,
   config and the existing split/labels are verified. No GitHub login/token is needed.
4. Run the dependency/GPU cell. It installs the pinned Ultralytics only in Colab,
   prints the actual torch/CUDA/GPU, and runs a tiny CUDA NMS compatibility check.
   If Colab asks for a Python session restart, restart then repeat the setup cells;
   they accept matching existing code/extraction/dataset and validate them again.
5. Run the archive cell with `SOURCE_MODE='upload'` and select the existing
   `ml/data/transmission line object detection.zip`. Alternatively choose `'hf'`:
   only the target ZIP is fetched. Its hash must match the audited archive even when
   HF revision main is used. No new labels, exclusions or split are computed.
6. Run export/preflight. Expected counts: train 3109, val 389, test 389. This validates
   file hashes/labels; test images are not evaluated by a model.
7. Keep `USE_DRIVE_BACKUP=True` for persistent checkpoints, run the Drive cell, and
   complete Google account authorization yourself. Raw images stay in /content.
   Default backup: `MyDrive/LineSightAI/runs/baseline640_v1/`. It must not exist.
   Set a new RUN_ID for any repeat. Drive is optional, but without it a complete VM
   reset loses all results not yet downloaded.
8. Inspect checks, then set **START_TRAINING=True** in the manual-start cell and run
   that cell. Until this edit, even executing the cell does not train/download weights.
   The Python runner is called with the frozen data.yaml and config.
9. After completion, run the export/download cell. Download **baseline640_v1.zip**;
   when Drive is enabled, the same ZIP is copied to the backup folder. Put the ZIP
   in local ignored `ml/runs/` and return for analysis. Do not tune on test.

The notebook has not been executed in Colab UI yet. Notebook schema/Python syntax,
bundle hashes and the default no-training guard are checked locally. Real CUDA
training and compatibility are verified by the user at first launch.

### What the run retains

```text
baseline640_v1/
  training/weights/best.pt, last.pt, epoch*.pt
  training/results.csv, args.yaml, results.png, train/val plots
  validation/                 # confusion matrices, curves, validation plots/JSON
  validation_metrics.json     # real best.pt metrics on val only
  val_predictions.json
  examples/                  # up to 6 TP / FP / FN images per category, if present
  error_analysis.json        # fixed conf=.25, greedy class-0 matching IoU=.5
  requested_config.json, effective_config.json
  dataset_manifest.json, manifest.json
  environment.json, pip-freeze.txt, nvidia-smi.txt
  training.log
  progress.json
  errors.txt, backup_errors.txt  # only on failure
```

Source code hashes, base Git SHA (uncommitted source is explicit), actual pretrained
weights SHA256, GPU/VRAM and exact dataset manifest are retained. Ultralytics args.yaml
records resolved defaults beyond the explicit config. No environment secrets or
GitHub credentials are passed to the runner.

FP/FN are discrepancies relative to possibly incomplete annotations, not adjudicated
real-world failures. No verified negative images and residual scene similarity limit
interpretation of internal precision/mAP. Predictions on real drone video are separate.
Empty example categories are reported as zero rather than fabricated.

### Checkpoints, interruptions and OOM

`save=True` keeps last/best and `save_period=5` retains periodic epoch*.pt. In the
pinned Ultralytics implementation their epoch suffix is zero-based. On-model-save
copies compact run artifacts to Drive after completed epoch 1, every 5 completed
epochs and at the end. Dataset views are excluded from both backup and ZIP.
This reduces loss but cannot protect progress after the last successful copy.
Check backup_errors.txt if Drive sync warns.

Final best/last may have optimizer state stripped by Ultralytics; keep periodic
epoch*.pt as recovery candidates. Exact resume is not implemented or claimed here:
after a VM loss, preserve the backup and inspect its checkpoint/environment before
choosing a recovery command. No automatic restart from scratch occurs.

On CUDA OOM, retain the failed run, set `BATCH=8` and a new RUN_ID, then rerun the
manual-start cell. The dataset and test split stay unchanged. The runner's finally
block attempts backup/ZIP on catchable errors; a hard VM shutdown cannot run finally.
If a process was killed but its /content files remain, the export cell can still ZIP
those files. With no backup, download before ending the session.

CPU-only checks:

```powershell
python ml/train.py preflight --data ml/data/yolo-czjyz-ps-v1/data.yaml --config ml/configs/baseline_czjyz_ps_v1.json
python -m pytest -q ml/tests/test_dataset.py ml/tests/test_yolo_dataset.py ml/tests/test_train.py
```

Regenerate the same bundle format when code changes (also update notebook SHA256):

```powershell
python ml/prepare_yolo.py bundle --plan ml/runs/czjyz-ps-audit-v1/dataset_plan.json --output ml/runs/czjyz-ps-audit-v1/colab_baseline_v1_bundle_new.zip --training
```

Reference implementation: [YOLO11 models](https://docs.ultralytics.com/models/yolo11/),
[pinned trainer/checkpoints](https://github.com/ultralytics/ultralytics/blob/v8.3.228/ultralytics/engine/trainer.py),
[pinned training defaults](https://github.com/ultralytics/ultralytics/blob/v8.3.228/ultralytics/cfg/default.yaml).
