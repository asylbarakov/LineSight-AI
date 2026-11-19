"""Local relative inverse depth, cache, and conservative planar defect protection."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image
from setup_depth import MODEL_DIR, MODEL_ID

ROOT=Path(__file__).resolve().parent
_model=None
_processor=None


def estimate_depth(image, status=lambda text: None):
    import cv2
    import torch
    from transformers import AutoModelForDepthEstimation, DPTImageProcessor
    global _model, _processor
    if not (MODEL_DIR/'model.safetensors').is_file():
        raise RuntimeError('Модель глубины не установлена. Запустите ./.venv/Scripts/python.exe setup_depth.py один раз с доступом к интернету.')
    provenance=json.loads((MODEL_DIR/'provenance.json').read_text())
    key=hashlib.sha256(image.tobytes()+str(image.size).encode()+provenance['revision'].encode()+b'518-v1').hexdigest()
    cache=ROOT/'.cache'/'depth';cache.mkdir(parents=True,exist_ok=True)
    file=cache/(key+'.npy')
    if file.exists():
        status('Карта глубины из кэша')
        return np.load(file,allow_pickle=False),{**provenance,'cache_hit':True,'cache_key':key}
    status('Загрузка модели глубины в память')
    if _model is None:
        torch.set_num_threads(min(8,os.cpu_count() or 4))
        _processor=DPTImageProcessor.from_pretrained(MODEL_DIR,local_files_only=True)
        _model=AutoModelForDepthEstimation.from_pretrained(MODEL_DIR,local_files_only=True,use_safetensors=True).eval()
        _model.to('cuda' if torch.cuda.is_available() else 'cpu')
    device=next(_model.parameters()).device
    status(f'Оценка глубины ({device})')
    inputs=_processor(images=image,return_tensors='pt').to(device)
    with torch.inference_mode():
        raw=_model(**inputs).predicted_depth[0].float().cpu().numpy()
    if not np.isfinite(raw).all(): raise RuntimeError('Модель вернула некорректную карту глубины.')
    lo,hi=np.percentile(raw,[2,98])
    if hi-lo<1e-6: raise RuntimeError('Модель не смогла различить глубину сцены.')
    near=np.clip((raw-lo)/(hi-lo),0,1).astype('f4')
    # Keep a moderate dense geometry grid; original full-resolution RGB is the texture.
    ratio=min(1.,1280/max(image.size))
    size=tuple(max(2,round(v*ratio)) for v in image.size)
    near=cv2.resize(near,size,interpolation=cv2.INTER_CUBIC).clip(0,1)
    near=cv2.bilateralFilter(near,5,.06,3)
    np.save(file,near)
    return near,{**provenance,'cache_hit':False,'cache_key':key,'device':str(device)}


def protect_defects(near, objects, source_size):
    """Flatten union of overlapping boxes + margin; blend only outside protected cores."""
    import cv2
    height,width=near.shape
    sw,sh=source_size
    mask=np.zeros((height,width),np.uint8)
    for obj in objects:
        x1,y1,x2,y2=obj['bbox']
        # Include vertices just outside the bbox so every triangle inside it is planar.
        left=max(0,int(np.floor(x1/sw*(width-1)))-3)
        top=max(0,int(np.floor(y1/sh*(height-1)))-3)
        right=min(width,int(np.ceil(x2/sw*(width-1)))+4)
        bottom=min(height,int(np.ceil(y2/sh*(height-1)))+4)
        mask[top:bottom,left:right]=1
    count,components=cv2.connectedComponents(mask)
    effective=near.copy()
    for label in range(1,count):
        region=(components==label)
        value=float(np.median(near[region]))
        outside=cv2.distanceTransform((~region).astype(np.uint8),cv2.DIST_L2,3)
        alpha=np.clip(1-outside/12,0,1)
        # Other protected cores must not be modified by a neighbour's feather.
        alpha[(mask>0)&~region]=0
        effective=effective*(1-alpha)+value*alpha
    return effective.astype('f4'),mask


def save_depth(out, raw, effective, protected, metadata):
    np.save(out/'depth_raw.npy',raw)
    np.save(out/'depth_effective.npy',effective)
    Image.fromarray(np.round(raw*65535).astype('uint16')).save(out/'depth_raw.png')
    Image.fromarray(np.round(effective*65535).astype('uint16')).save(out/'depth_effective.png')
    Image.fromarray(protected*255).save(out/'depth_protected.png')
    (out/'depth_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')


def stabilize_layers(near):
    """Three front-to-back surfaces avoid stretching across uncertain depth edges.

Each protected bbox has a constant estimate and therefore belongs wholly to one
surface. This is an explicit layered 2.5D approximation, not metric reconstruction.
"""
    labels=np.minimum((near*3).astype('uint8'),2)
    effective=near.copy()
    for label in range(3):
        mask=labels==label
        if mask.any():effective[mask]=float(np.median(near[mask]))
    return effective.astype('f4')
