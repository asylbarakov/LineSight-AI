"""Manual Colab baseline runner. 'preflight' is CPU-safe; only 'run' trains."""
import argparse
from collections import defaultdict
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import traceback
import zipfile

from prepare_yolo import validate_dataset


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha256(path):
    value=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            value.update(chunk)
    return value.hexdigest()


def preflight(data, config):
    import yaml
    data=Path(data).resolve(strict=True)
    settings=yaml.safe_load(data.read_text(encoding="utf-8"))
    root=data.parent
    if Path(settings.get("path","")).resolve()!=root:
        raise ValueError("data.yaml must name its actual dataset root; re-export after moving it")
    if settings.get("names")!={0:"czjyz_ps"}:
        raise ValueError("Expected exactly class 0 czjyz_ps")
    for split in ("train","val"):
        if settings.get(split)!=f"images/{split}":
            raise ValueError("Unexpected split path")
    checked=validate_dataset(root)
    if config["model"]!="yolo11n.pt" or config["epochs"] not in range(20,31) or config["imgsz"]!=640:
        raise ValueError("First baseline is fixed to yolo11n.pt, 640, 20–30 epochs")
    manifest=read_json(root/"manifest.json")
    return {"dataset_root":str(root),"dataset_manifest_sha256":sha256(root/"manifest.json"),
            "checked":checked,"train_count":manifest["split_counts"]["train"],
            "val_count":manifest["split_counts"]["val"],"model_evaluation_split":"val",
            "limitations":["No verified negative images", "Residual similar-scene leakage risk", "Target is local ceramic damage, not complete insulator"]}


def choose_batch(vram_bytes, requested="vram"):
    if vram_bytes < 6*1024**3:
        raise ValueError("GPU VRAM below 6 GiB; stop and review configuration")
    if requested not in ("vram",8,16):
        raise ValueError("Batch must be 8, 16 or vram")
    return (16 if vram_bytes>=14*1024**3 else 8) if requested=="vram" else requested


def iou(a,b):
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
    return intersection/union if union>0 else 0


def match_boxes(gt,predictions,threshold):
    """Fixed-threshold diagnostics, separate from Ultralytics mAP calculation."""
    remaining=set(range(len(gt)))
    tp,fp=[],[]
    for index in sorted(range(len(predictions)),key=lambda i:-predictions[i]["confidence"]):
        best=max(remaining,key=lambda j:iou(gt[j],predictions[index]["xyxy"]),default=None)
        if best is not None and iou(gt[best],predictions[index]["xyxy"])>=threshold:
            tp.append({"prediction":index,"ground_truth":best})
            remaining.remove(best)
        else:
            fp.append(index)
    return {"tp":tp,"fp":fp,"fn":sorted(remaining)}


def sync_artifacts(run_dir, backup_dir):
    """Copy compact artifacts/checkpoints, never the dataset; replace files atomically."""
    if backup_dir is None:
        return
    run_dir,backup_dir=Path(run_dir).resolve(),Path(backup_dir).resolve()
    if run_dir==backup_dir or backup_dir.is_relative_to(run_dir) or run_dir.is_relative_to(backup_dir):
        raise ValueError("Backup must be separate from the local run")
    for source in run_dir.rglob("*"):
        if source.relative_to(run_dir).parts[0]=="data_view" or not source.is_file() or source.is_symlink() or source.suffix==".zip":
            continue
        target=backup_dir/source.relative_to(run_dir)
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.stat().st_size==source.stat().st_size and target.stat().st_mtime_ns==source.stat().st_mtime_ns:
            continue
        temporary=target.with_name(target.name+".partial")
        shutil.copy2(source,temporary)
        temporary.replace(target)


def checkpoint_callback(run_dir,backup_dir,period):
    def callback(trainer):
        epoch=trainer.epoch+1
        if epoch==1 or epoch%period==0 or epoch==trainer.epochs:
            write_json(Path(run_dir)/"progress.json",{"completed_epoch":epoch,"planned_epochs":trainer.epochs})
            try:
                sync_artifacts(run_dir,backup_dir)
            except Exception:
                # Drive failure must be visible but must not discard local training.
                with (Path(run_dir)/"backup_errors.txt").open("a",encoding="utf-8") as stream:
                    traceback.print_exc(file=stream)
                print("WARNING: persistent backup failed; see backup_errors.txt",flush=True)
    return callback


def stage_training_view(dataset,output):
    """Isolate label caches from frozen source; never expose test to the trainer."""
    dataset,output=Path(dataset),Path(output)
    output.mkdir(exist_ok=False)
    for split in ("train","val"):
        for kind in ("images","labels"):
            target=output/kind/split
            target.mkdir(parents=True)
            for source in (dataset/kind/split).iterdir():
                if source.suffix.lower() not in ((".jpg",".jpeg",".png") if kind=="images" else (".txt",)):
                    continue
                destination=target/source.name
                if kind=="images":
                    destination.hardlink_to(source)
                else:
                    shutil.copyfile(source,destination)
    return output


class Tee:
    def __init__(self,*streams): self.streams=streams
    def write(self,text):
        for stream in self.streams:
            stream.write(text); stream.flush()
        return len(text)
    def flush(self):
        for stream in self.streams: stream.flush()
    def isatty(self): return False


def val_diagnostics(model,dataset,output,config):
    from PIL import Image,ImageDraw
    images=sorted((dataset/"images/val").iterdir())
    random.Random(config["seed"]).shuffle(images)
    examples=output/"examples"
    examples.mkdir()
    counts=defaultdict(int,{key:0 for key in ("tp","fp","fn","tp_images","fp_images","fn_images")})
    records=[]
    for path in images:
        with Image.open(path) as source:
            width,height=source.size
        label=dataset/"labels/val"/(path.stem+".txt")
        gt=[]
        for line in label.read_text().splitlines():
            _,cx,cy,w,h=map(float,line.split())
            gt.append([(cx-w/2)*width,(cy-h/2)*height,(cx+w/2)*width,(cy+h/2)*height])
        result=model.predict(str(path),imgsz=config["imgsz"],conf=config["error_conf"],device=0,verbose=False,save=False)[0]
        pred=[{"xyxy":box,"confidence":conf} for box,conf in zip(result.boxes.xyxy.cpu().tolist(),result.boxes.conf.cpu().tolist())]
        matched=match_boxes(gt,pred,config["error_iou"])
        records.append({"image":path.name,"gt":gt,"predictions":pred,"matches":matched})
        kinds=[kind for kind in ("tp","fp","fn") if matched[kind]]
        for kind in kinds:
            counts[kind]+=len(matched[kind])
            example_key=kind+"_images"
            if counts[example_key]>=config["examples_per_kind"]:
                continue
            with Image.open(path) as source: image=source.convert("RGB")
            draw=ImageDraw.Draw(image)
            for box in gt: draw.rectangle(box,outline="red",width=2)
            for item in pred:
                draw.rectangle(item["xyxy"],outline="#00ff40",width=2)
                draw.text(item["xyxy"][:2],f"{item['confidence']:.2f}",fill="#00ff40")
            image.save(examples/f"{kind}_{path.stem}.jpg",quality=90)
            counts[example_key]+=1
    write_json(output/"val_predictions.json",records)
    write_json(output/"error_analysis.json",{"split":"val","conf":config["error_conf"],"match_iou":config["error_iou"],
        "counts":dict(counts),"note":"FP/FN relative to incomplete annotations, not adjudicated truth. Zero examples of a kind is allowed; examples are never fabricated. Red=GT, green=prediction."})


def train(args):
    config=read_json(args.config)
    if args.batch is not None: config["batch"]=args.batch
    checked=preflight(args.data,config)
    if importlib.metadata.version("ultralytics")!=config["ultralytics_version"]:
        raise ValueError("Ultralytics version differs from pinned baseline")
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU unavailable; refusing CPU training")
    props=torch.cuda.get_device_properties(0)
    free_vram,_=torch.cuda.mem_get_info(0)
    batch=choose_batch(min(props.total_memory,free_vram),config["batch"])
    output=args.output.resolve()
    dataset=Path(checked["dataset_root"])
    if output==dataset or output.is_relative_to(dataset) or dataset.is_relative_to(output):
        raise ValueError("Run must be outside dataset")
    if args.backup_dir and args.backup_dir.exists():
        raise FileExistsError("Use a new persistent backup directory for each run")
    if args.backup_dir:
        backup=args.backup_dir.resolve()
        if backup==dataset or backup.is_relative_to(dataset) or dataset.is_relative_to(backup):
            raise ValueError("Backup must not overlap dataset")
    output.mkdir(parents=True,exist_ok=False)
    from check_env import check_environment
    write_json(output/"environment.json",check_environment())
    if shutil.which("nvidia-smi"):
        gpu_report=subprocess.run(["nvidia-smi"],capture_output=True,text=True,check=False)
        (output/"nvidia-smi.txt").write_text(gpu_report.stdout+gpu_report.stderr,encoding="utf-8")
    freeze=subprocess.check_output([sys.executable,"-m","pip","freeze"],text=True)
    (output/"pip-freeze.txt").write_text(freeze,encoding="utf-8")
    shutil.copyfile(dataset/"manifest.json",output/"dataset_manifest.json")
    shutil.copyfile(args.config,output/"requested_config.json")
    view=stage_training_view(dataset,output/"data_view")
    # Restrict model-facing YAML to train/val. No test loader during this experiment.
    train_yaml=output/"train_data.yaml"
    train_yaml.write_text("path: "+json.dumps(view.as_posix())+"\ntrain: images/train\nval: images/val\nnames:\n  0: czjyz_ps\n",encoding="utf-8")
    bundle_manifest=Path(__file__).with_name("bundle_manifest.json")
    manifest={"status":"starting","started_at":datetime.now(timezone.utc).isoformat(),"model":config["model"],
              "gpu":{"name":props.name,"vram_bytes":props.total_memory,"free_vram_bytes_at_start":free_vram},
              "torch":torch.__version__,"torch_cuda":torch.version.cuda,"ultralytics":config["ultralytics_version"],
              "dataset":checked,"dataset_provenance":read_json(dataset/"manifest.json").get("provenance"),
              "script_sha256":sha256(__file__),"batch":batch,"test_used_for_model_evaluation":False}
    manifest["code_bundle"]=read_json(bundle_manifest) if bundle_manifest.is_file() else None
    manifest["git_sha"]=(manifest["code_bundle"] or manifest.get("dataset_provenance") or {}).get("git_sha") or (manifest.get("dataset_provenance") or {}).get("git_head")
    write_json(output/"manifest.json",manifest)
    with (output/"training.log").open("w",encoding="utf-8",buffering=1) as log, redirect_stdout(Tee(sys.stdout,log)),redirect_stderr(Tee(sys.stderr,log)):
        try:
            from ultralytics import YOLO,settings
            settings.update({"sync":False,"wandb":False,"mlflow":False,"comet":False,"clearml":False,"neptune":False,"tensorboard":False})
            model=YOLO(config["model"])
            weights=Path(config["model"])
            manifest["initial_weights_sha256"]=sha256(weights) if weights.is_file() else None
            if manifest["initial_weights_sha256"] is None:
                raise FileNotFoundError("Cannot record downloaded pretrained weights hash")
            model.add_callback("on_model_save",checkpoint_callback(output,args.backup_dir,config["save_period"]))
            names=("imgsz","epochs","seed","deterministic","optimizer","lr0","weight_decay","workers","amp","patience","save_period","close_mosaic","cache")
            actual={name:config[name] for name in names}
            actual.update(data=str(train_yaml),batch=batch,device=0,project=str(output),name="training",exist_ok=False,
                          pretrained=True,save=True,plots=True,val=True,split="val")
            write_json(output/"effective_config.json",actual)
            write_json(output/"manifest.json",manifest)
            sync_artifacts(output,args.backup_dir)
            model.train(**actual)
            best=output/"training/weights/best.pt"
            evaluated=YOLO(str(best))
            metrics=evaluated.val(data=str(train_yaml),split="val",imgsz=config["imgsz"],batch=batch,device=0,conf=0.001,
                                  plots=True,save_json=True,project=str(output),name="validation",exist_ok=False)
            write_json(output/"validation_metrics.json",metrics.results_dict)
            val_diagnostics(evaluated,dataset,output,config)
            manifest.update(status="complete",best_weights_sha256=sha256(best))
        except BaseException:
            manifest["status"]="interrupted_or_failed"
            (output/"errors.txt").write_text(traceback.format_exc(),encoding="utf-8")
            raise
        finally:
            manifest["finished_at"]=datetime.now(timezone.utc).isoformat()
            write_json(output/"manifest.json",manifest)
            log.flush()
            # Failure here is visible; local results are still retained.
            try: sync_artifacts(output,args.backup_dir)
            except Exception:
                (output/"backup_errors.txt").write_text(traceback.format_exc(),encoding="utf-8")
            export_results(output)
    print("Run saved:",output,"ZIP:",output.with_suffix(".zip"))


def export_results(output):
    output=Path(output)
    target=output.with_suffix(".zip")
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        for path in output.rglob("*"):
            if path.relative_to(output).parts[0]!="data_view" and path.is_file() and not path.is_symlink():
                archive.write(path,path.relative_to(output))
    return target


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest="command",required=True)
    for name in ("preflight","run"):
        item=subs.add_parser(name)
        item.add_argument("--data",type=Path,required=True)
        item.add_argument("--config",type=Path,required=True)
        if name=="run":
            item.add_argument("--output",type=Path,required=True)
            item.add_argument("--backup-dir",type=Path)
            item.add_argument("--batch",type=int,choices=(8,16))
    item=subs.add_parser("export")
    item.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.command=="preflight": print(json.dumps(preflight(args.data,read_json(args.config)),indent=2))
    elif args.command=="run": train(args)
    else: print(export_results(args.output))


if __name__=="__main__":
    main()
