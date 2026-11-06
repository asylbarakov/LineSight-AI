"""Focused czjyz_ps baseline preparation. Never trains or edits VOC sources."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import zipfile

TARGET = "czjyz_ps"
SEED = 20261103


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def letterbox_box(obj, imgsz, scaleup=True):
    """Square letterbox, scaleup=True, no augmentation; padding changes no box sizes."""
    width, height = obj["actual_size"]
    scale = imgsz / max(width, height)
    if not scaleup:
        scale = min(scale,1)
    return obj["width_px"] * scale, obj["height_px"] * scale


def size_statistics(objects):
    from voc_dataset import distribution
    result = {"object_count": len(objects), "assumption": "Square letterbox with scaleup=True, no augmentation; dimension rounding ignored"}
    for size in (None, 640, 960):
        pairs = [(o["width_px"], o["height_px"]) if size is None else letterbox_box(o, size) for o in objects]
        short = [min(w,h) for w,h in pairs]
        result[str(size or "jpeg")] = {
            "width": distribution([w for w,h in pairs]), "height": distribution([h for w,h in pairs]),
            "short_side": distribution(short),
            "short_side_bins": {"lt8": sum(v < 8 for v in short), "8_to_16": sum(8 <= v < 16 for v in short),
                                "16_to_32": sum(16 <= v < 32 for v in short), "gte32": sum(v >= 32 for v in short)}}
    for size in (640,960):
        result[f"{size}_no_upscale_short_side"] = distribution([min(letterbox_box(o,size,False)) for o in objects])
    return result


class Groups:
    def __init__(self, names):
        self.parent = {name: name for name in names}

    def find(self, name):
        if self.parent[name] != name:
            self.parent[name] = self.find(self.parent[name])
        return self.parent[name]

    def union(self, a, b):
        x, y = self.find(a), self.find(b)
        self.parent[max(x,y)] = min(x,y)


def perceptual_features(path):
    import numpy as np
    from PIL import Image
    with Image.open(path) as image:
        gray = image.convert("L")
        pixels = np.asarray(gray.resize((32,32)), dtype=float)
        d = np.asarray(gray.resize((9,8)), dtype=float)
        size = list(image.size)
    positions = np.arange(32)
    basis = np.cos(math.pi / 32 * (positions[None,:] + .5) * positions[:,None])
    low = (basis @ pixels @ basis.T)[:8,:8].flatten()
    low[0] = 0
    bits = low > np.median(low[1:])
    bits[0] = False
    pack = lambda values: sum(int(value) << i for i,value in enumerate(values))
    return {"phash": pack(bits), "dhash": pack((d[:,1:] > d[:,:-1]).flatten()), "size": size, "sha256": digest(path)}


def near_pairs(features, radius=8):
    """BK-tree pHash candidates, confirmed by dHash and aspect ratio; heuristic only."""
    tree = None
    pairs = []
    for name in sorted(features):
        feature = features[name]
        value = feature["phash"]
        pending = [tree] if tree else []
        while pending:
            node = pending.pop()
            distance = (value ^ node[0]).bit_count()
            if distance <= radius:
                for other in node[1]:
                    f = features[other]
                    ratio = (feature["size"][0]/feature["size"][1]) / (f["size"][0]/f["size"][1])
                    dd = (feature["dhash"] ^ f["dhash"]).bit_count()
                    if dd <= 12 and abs(ratio-1) <= .02:
                        pairs.append({"a": other, "b": name, "phash_distance": distance, "dhash_distance": dd})
            pending.extend(child for edge,child in node[2].items() if distance-radius <= edge <= distance+radius)
        if tree is None:
            tree = [value, [name], {}]
        else:
            node = tree
            while True:
                distance = (value ^ node[0]).bit_count()
                if distance == 0:
                    node[1].append(name)
                    break
                if distance not in node[2]:
                    node[2][distance] = [value, [name], {}]
                    break
                node = node[2][distance]
    return pairs


def build_groups(report, features):
    groups = Groups(features)
    for members in report["exact_duplicate_image_groups"]:
        for member in members[1:]:
            groups.union(members[0], member)
    pairs = near_pairs(features)
    for pair in pairs:
        groups.union(pair["a"], pair["b"])
    # Named acquisition batches are kept together; voc1..voc10 are packing folders,
    # not scene IDs. IMG_* filenames do not establish acquisition-session identity.
    batches = defaultdict(list)
    for name in features:
        parts = Path(name).parts
        if len(parts) > 2 and not parts[1].lower().startswith("voc"):
            batches[parts[1]].append(name)
    for members in batches.values():
        for member in members[1:]:
            groups.union(members[0], member)
    return {name: groups.find(name) for name in features}, pairs


def select_audit(report):
    targets = defaultdict(list)
    for obj in report["objects"]:
        if obj["class"] == TARGET:
            targets[obj["image"]].append(obj)
    rng = random.Random(SEED)
    selected = {}
    buckets = defaultdict(list)
    for name, objects in sorted(targets.items()):
        shortest = min(min(letterbox_box(o,640)) for o in objects)
        key = "lt8" if shortest < 8 else "8_to_16" if shortest < 16 else "16_to_32" if shortest < 32 else "gte32"
        buckets[key].append(name)
    for key in ("lt8", "8_to_16", "16_to_32", "gte32"):
        candidates = buckets[key][:]
        rng.shuffle(candidates)
        for name in candidates[:6]:
            selected[name] = "size_stratum_" + key
    remaining = sorted(set(targets)-set(selected))
    rng.shuffle(remaining)
    for name in remaining[:8]:
        selected[name] = "random_seeded"
    conflicts = [group for group in report["duplicate_groups_with_different_projectable_labels"] if any(p in targets for p in group)]
    rng.shuffle(conflicts)
    for group in conflicts:
        for name in sorted(group)[:2]:
            if name not in selected:
                selected[name] = "conflicting_exact_duplicate"
        if len(selected) >= 48:
            break
    return [{"id": f"A{i:02d}", "image": name, "selection": reason,
             "target_boxes": targets.get(name, []), "decision": "pending", "note": ""}
            for i,(name,reason) in enumerate(list(selected.items())[:48],1)]


def audit_sheets(root, review, report, output):
    from PIL import Image, ImageDraw
    boxes = defaultdict(list)
    for obj in report["objects"]:
        boxes[obj["image"]].append(obj)
    output = Path(output)
    for offset in range(0,len(review),6):
        sheet = Image.new("RGB", (1500, 900), "#dddddd")
        for index,item in enumerate(review[offset:offset+6]):
            with Image.open(Path(root)/item["image"]) as source:
                original = source.convert("RGB")
            image = original.copy()
            draw = ImageDraw.Draw(image)
            for obj in boxes[item["image"]]:
                color = "#00ff40" if obj["class"] == TARGET else "#ff40ff"
                draw.rectangle(obj["image_xyxy"], outline=color, width=3)
            image.thumbnail((490,345))
            tile = Image.new("RGB", (500,450), "white")
            tile.paste(image,((500-image.width)//2,55))
            d = ImageDraw.Draw(tile)
            d.text((5,5), f"{item['id']} {item['selection']} | target={len(item['target_boxes'])}", fill="black")
            d.text((5,23), f"{item['decision']}: {item['note'][:68]}", fill="black")
            if item["target_boxes"]:
                obj = min(item["target_boxes"], key=lambda o:o["relative_area"])
                x1,y1,x2,y2 = obj["image_xyxy"]
                margin = max(12, .4*max(x2-x1,y2-y1))
                crop = original.crop((max(0,int(x1-margin)),max(0,int(y1-margin)),min(original.width,math.ceil(x2+margin)),min(original.height,math.ceil(y2+margin))))
                crop.thumbnail((150,125))
                tile.paste(crop,(345,320))
                d.rectangle((343,318,498,448),outline="red",width=2)
            sheet.paste(tile,((index%3)*500,(index//3)*450))
        sheet.save(output/f"semantic_{offset//6+1:02d}.jpg",quality=91)


def audit(args):
    report = load(args.report)
    output = args.output
    output.mkdir(parents=True,exist_ok=False)
    targets = [o for o in report["objects"] if o["class"] == TARGET]
    save(output/"bbox_sizes.json",size_statistics(targets))
    review = select_audit(report)
    save(output/"semantic_review.json",review)
    audit_sheets(report["dataset_root"], review, report, output)
    features = {}
    names = [name for name in report["files"] if Path(name).suffix.lower() in (".jpg",".jpeg",".png")]
    for index,name in enumerate(names,1):
        features[name] = perceptual_features(Path(report["dataset_root"])/name)
        if index%1000 == 0:
            print(f"Perceptual hashes: {index}/{len(names)}",flush=True)
    save(output/"image_features.json",features)
    groups,pairs = build_groups(report,features)
    save(output/"leakage_groups.json",groups)
    save(output/"near_duplicate_pairs.json",pairs)
    print("Audit images and duplicate groups ready; fill review decisions before plan/export.")


def make_plan(report, features, groups, review):
    if not review or any(item["decision"] == "pending" for item in review):
        raise ValueError("Finish semantic review first")
    objects = defaultdict(list)
    for obj in report["objects"]:
        objects[obj["image"]].append(obj)
    bad_annotations = {item["annotation"] for item in report["invalid_annotations"]}
    conflict_images = {p for members in report["duplicate_groups_with_different_projectable_labels"] for p in members}
    reviewed_bad = {item["image"] for item in review if item["decision"] != "accept"}
    bad_groups = {groups[name] for name in conflict_images|reviewed_bad if name in groups}
    # Exact duplicates with different target coordinates are also ambiguous.
    for members in report["exact_duplicate_image_groups"]:
        signatures = {tuple(sorted(tuple(round(v/d,4) for v,d in zip(o["image_xyxy"],o["actual_size"]*2))
                                    for o in objects[name] if o["class"]==TARGET)) for name in members}
        if len(signatures) > 1:
            bad_groups.update(groups[name] for name in members)
    excluded, candidates = [], []
    hashes_seen = set()
    for name in sorted(features):
        rows = objects[name]
        target = [o for o in rows if o["class"]==TARGET]
        reasons = []
        if not target:
            reasons.append("no_verified_target_positive_not_a_negative")
        if any(o["annotation"] in bad_annotations for o in rows):
            reasons.append("image_has_invalid_or_uncertain_annotation")
        if any(o["class"] != TARGET for o in rows):
            reasons.append("mixed_defect_classes_excluded_conservatively")
        if groups[name] in bad_groups:
            reasons.append("ambiguous_duplicate_or_semantic_review_group")
        if any(min(letterbox_box(o,640)) < 8 for o in target):
            reasons.append("target_short_side_lt8_at_imgsz640")
        if any(o["short_side_px"] < 8 for o in target):
            reasons.append("native_target_short_side_lt8")
        sha = features[name]["sha256"]
        if not reasons and sha in hashes_seen:
            reasons.append("redundant_exact_duplicate")
        if reasons:
            excluded.append({"image":name,"group":groups[name],"reasons":reasons})
            continue
        hashes_seen.add(sha)
        labels = []
        for obj in target:
            x1,y1,x2,y2 = obj["image_xyxy"]
            w,h = obj["actual_size"]
            label = [0,(x1+x2)/(2*w),(y1+y2)/(2*h),(x2-x1)/w,(y2-y1)/h]
            if label not in labels:
                labels.append(label)
        candidates.append({"image":name,"group":groups[name],"sha256":sha,
                           "annotation":sorted({o['annotation'] for o in target}),"labels":labels})
    group_members = defaultdict(list)
    for row in candidates:
        group_members[row["group"]].append(row)
    keys = sorted(group_members)
    random.Random(SEED).shuffle(keys)
    keys.sort(key=lambda key:-len(group_members[key]))
    target_counts = {"train":.8*len(candidates),"val":.1*len(candidates),"test":.1*len(candidates)}
    counts = Counter()
    for group in keys:
        split = max(target_counts,key=lambda key:(target_counts[key]-counts[key])/target_counts[key])
        for row in group_members[group]:
            row["split"] = split
        counts[split] += len(group_members[group])
    return {"version":"yolo-czjyz-ps-v1","class_names":[TARGET],"seed":SEED,"source_archive":report["archive_provenance"],
            "source_annotation_sha256":report["source_annotation_sha256"],"included":candidates,"excluded":excluded,
            "split_counts":dict(counts),"split_objects":{split:sum(len(row['labels']) for row in candidates if row['split']==split) for split in target_counts},
            "review":review,"rules":{"negative_images":False,"min_target_short_side_at_640":8,
            "split_grouping":"exact SHA256 + pHash<=8 AND dHash<=12, aspect ratio within 2%; named acquisition batches",
            "limitations":"Perceptual hashes do not guarantee discovery of all adjacent views. Full source scene IDs are unavailable. Only the stratified sample was semantically reviewed.",
            "bbox_meaning":"local ceramic damage, not complete insulator","pixel_convention":"raw VOC xyxy divided by declared canvas; no +/-1 offset"},
            "source_annotation_issues":{key:report[key] for key in ("invalid_annotations","missing_referenced_files","empty_annotations","images_without_xml","filename_reference_issues")}}


def export_plan(plan, source, output, hardlink=False):
    source = Path(source).resolve()
    output = Path(output).resolve()
    if source == output or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Output must be separate from source")
    if set(plan["split_counts"]) != {"train","val","test"}:
        raise ValueError("All three splits are required")
    group_splits = defaultdict(set)
    for row in plan["included"]:
        if row["split"] not in ("train","val","test"):
            raise ValueError("Unknown split")
        group_splits[row["group"]].add(row["split"])
        path = (source/row["image"]).resolve()
        if not path.is_relative_to(source) or not path.is_file() or digest(path)!=row["sha256"]:
            raise ValueError(f"Source/hash mismatch: {row['image']}")
        for label in row["labels"]:
            if len(label)!=5 or label[0]!=0 or not all(math.isfinite(x) for x in label):
                raise ValueError("Invalid YOLO label")
            _,cx,cy,w,h = label
            if not (w>0 and h>0 and 0<=cx-w/2<=cx+w/2<=1 and 0<=cy-h/2<=cy+h/2<=1):
                raise ValueError("Out-of-bounds YOLO label")
    if any(len(splits)!=1 for splits in group_splits.values()):
        raise ValueError("Cross-split duplicate group")
    output.mkdir(parents=True,exist_ok=False)
    for split in ("train","val","test"):
        (output/"images"/split).mkdir(parents=True)
        (output/"labels"/split).mkdir(parents=True)
    for row in plan["included"]:
        name = hashlib.sha256(row["image"].encode()).hexdigest()[:24]
        src = source/row["image"]
        dest = output/"images"/row["split"]/(name+src.suffix.lower())
        if hardlink:
            dest.hardlink_to(src)
        else:
            shutil.copyfile(src,dest)
        text = "\n".join(" ".join(["0"]+[f"{v:.10f}" for v in label[1:]]) for label in row["labels"])+"\n"
        (output/"labels"/row["split"]/(name+".txt")).write_text(text,encoding="utf-8")
    (output/"data.yaml").write_text("path: "+json.dumps(output.as_posix())+"\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: czjyz_ps\n",encoding="utf-8")
    save(output/"manifest.json",{**plan,"storage":"hardlinks_read_only_do_not_edit_images" if hardlink else "copies"})


def validate_dataset(output):
    output=Path(output)
    plan=load(output/"manifest.json")
    groups=defaultdict(set)
    hashes=defaultdict(set)
    counts=Counter()
    for row in plan["included"]:
        split=row["split"]
        name=hashlib.sha256(row["image"].encode()).hexdigest()[:24]
        path=output/"images"/split/(name+Path(row["image"]).suffix.lower())
        if digest(path)!=row["sha256"]:
            raise ValueError("Exported image hash mismatch")
        label=output/"labels"/split/(name+".txt")
        values=[[float(v) for v in line.split()] for line in label.read_text().splitlines()]
        if len(values)!=len(row["labels"]) or any(len(a)!=5 or not all(math.isfinite(x) for x in a)
                or any(abs(x-y)>1e-9 for x,y in zip(a,b)) for a,b in zip(values,row["labels"])):
            raise ValueError("Exported labels differ from frozen plan")
        groups[row["group"]].add(split)
        hashes[row["sha256"]].add(split)
        counts[split]+=1
    if any(len(v)>1 for v in list(groups.values())+list(hashes.values())):
        raise ValueError("Cross-split image/group leakage")
    for split,count in counts.items():
        if len(list((output/"images"/split).iterdir()))!=count or len(list((output/"labels"/split).iterdir()))!=count:
            raise ValueError("Unexpected/missing image or label files")
    if dict(counts)!=plan["split_counts"]:
        raise ValueError("Split counts differ from manifest")
    return {"status":"passed","images":dict(counts),"objects":plan["split_objects"],"cross_split_group_or_exact_hash_overlap":0}


def create_bundle(plan_path, output, training=False):
    """Ship the reviewed uncommitted code and frozen plan; no images or credentials."""
    scripts=("prepare_yolo.py","download_dataset.py","check_env.py","voc_dataset.py")
    files={name:Path(__file__).with_name(name).read_bytes() for name in scripts}
    if training:
        for name in ("train.py","requirements-colab.txt"):
            files[name]=Path(__file__).with_name(name).read_bytes()
        files["baseline_czjyz_ps_v1.json"]=(Path(__file__).parent/"configs/baseline_czjyz_ps_v1.json").read_bytes()
    files["plan.json"]=Path(plan_path).read_bytes()
    metadata={"files":{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
              "purpose":"manual_training" if training else "dataset_preparation",
              "git_sha":load(plan_path).get("provenance",{}).get("git_head"),
              "code_uncommitted":True,
              "note":"Frozen local source bundle, no remote publishing or credentials required."}
    with zipfile.ZipFile(output,"x",compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():
            archive.writestr(name,data)
        archive.writestr("bundle_manifest.json",json.dumps(metadata,indent=2))
    return digest(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command",required=True)
    p = sub.add_parser("audit")
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p = sub.add_parser("plan")
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--audit",type=Path,required=True)
    p.add_argument("--review",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p = sub.add_parser("export")
    p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--hardlink",action="store_true")
    p=sub.add_parser("validate")
    p.add_argument("--dataset",type=Path,required=True)
    p=sub.add_parser("bundle")
    p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--training",action="store_true")
    args = parser.parse_args()
    if args.command=="audit":
        audit(args)
    elif args.command=="plan":
        if args.output.exists():
            raise FileExistsError(args.output)
        plan=make_plan(load(args.report),load(args.audit/"image_features.json"),load(args.audit/"leakage_groups.json"),load(args.review))
        save(args.output,plan)
        print(plan["split_counts"],plan["split_objects"])
    elif args.command=="export":
        export_plan(load(args.plan),args.source,args.output,args.hardlink)
        print("Dataset exported; training was not run")
    elif args.command=="validate":
        print(json.dumps(validate_dataset(args.dataset),indent=2))
    else:
        print("Bundle SHA256:",create_bundle(args.plan,args.output,args.training))


if __name__=="__main__":
    main()
