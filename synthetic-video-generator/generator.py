"""Deterministic crop camera and ground truth; all coordinates refer to oriented pixels."""
import hashlib
import json
import math
import time
import zipfile
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageOps
from camera import drone_matrix, project


def validate(config, size):
    w, h = size
    duration = float(config.get('duration', 30))
    fps = int(config.get('fps', 25))
    width = int(config.get('width', 1280))
    if not math.isfinite(duration) or not 1 <= duration <= 180:
        raise ValueError('Длительность: от 1 до 180 секунд.')
    if fps not in (15, 25, 30) or width not in (640, 1280, 1920):
        raise ValueError('Неподдерживаемое разрешение или FPS.')
    objects = config.get('objects', [])
    if not isinstance(objects, list) or not 1 <= len(objects) <= 100:
        raise ValueError('Добавьте от 1 до 100 рамок.')
    clean = []
    for i, obj in enumerate(objects):
        box = list(map(float, obj['bbox']))
        if len(box) != 4 or not all(map(math.isfinite, box)):
            raise ValueError('bbox должен содержать четыре конечных числа.')
        x1, y1, x2, y2 = box
        if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
            raise ValueError('Рамка должна находиться внутри фото (xyxy в пикселях).')
        label = str(obj.get('label', '')).strip()
        if not label or len(label) > 160:
            raise ValueError('Укажите название дефекта (до 160 символов).')
        clean.append({'object_id': i + 1, 'label': label, 'bbox': box})
    motion = config.get('motion', 'drone')
    if motion not in ('depth', 'drone', 'calm', 'classic'):
        raise ValueError('Неизвестный профиль камеры.')
    parallax_strength=float(config.get('parallax_strength', 1))
    if not math.isfinite(parallax_strength) or not .2 <= parallax_strength <= 1.5:
        raise ValueError('Сила параллакса: от 0.2 до 1.5.')
    focus_points=config.get('focus_points',[])
    if not isinstance(focus_points,list) or len(focus_points)>14:
        raise ValueError('Дополнительных точек осмотра должно быть не больше 14.')
    focus=[]
    for i,point in enumerate(focus_points):
        box=list(map(float,point['bbox']))
        if len(box)!=4 or not all(map(math.isfinite,box)) or not (0<=box[0]<box[2]<=w and 0<=box[1]<box[3]<=h):
            raise ValueError('Рамка точки осмотра должна находиться внутри фото (xyxy).')
        label=str(point.get('label','')).strip() or f'Точка осмотра {i+1}'
        if len(label)>160:raise ValueError('Название точки осмотра: до 160 символов.')
        focus.append({'point_id':i+1,'label':label,'bbox':box})
    overview=config.get('overview',False)
    if not isinstance(overview,bool):raise ValueError('overview должен быть boolean.')
    effects={}
    for key in ('blur_strength','noise_strength'):
        value=float(config.get(key,0))
        if not math.isfinite(value) or not 0<=value<=1:raise ValueError(f'{key}: от 0 до 1.')
        effects[key]=value
    if overview:
        base=min(w,h*16/9)
        if base*base*9/16/(w*h)<.9:
            raise ValueError('Общий план 90–100% требует фото, близкого к 16:9. Для этого соотношения сторон кадр 16:9 обрежет больше 10% фото.')
    if focus or overview:
        minimum=4*(len(clean)+len(focus)+int(overview))
        if duration<minimum:
            raise ValueError(f'Для осмотра всех {len(clean)+len(focus)+int(overview)} целей нужно минимум {minimum} секунд (переходы и фиксация). Увеличьте длительность или уменьшите число точек.')
        for target in clean+focus:
            if target['bbox'][3]-target['bbox'][1]>min(h,w*9/16) or target['bbox'][2]-target['bbox'][0]>min(w,h*16/9):
                raise ValueError('Одна из рамок слишком велика для полного осмотра в кадре 16:9. Уменьшите её или отключите дополнительные точки.')
    return {'duration': duration, 'fps': fps, 'width': width, 'motion': motion,
            'focus_points':focus,
            'overview':overview, **effects,
            'parallax_strength':parallax_strength,
            'height': width * 9 // 16, 'objects': clean, 'seed': int(config.get('seed', 42))}


def camera_path(size, objects, count, seed):
    """Visit context, each defect, then context. Continuous cubic-eased crop path."""
    iw, ih = size
    base_w = min(iw, ih * 16 / 9)
    rng = np.random.default_rng(seed)

    def crop(cx, cy, width):
        width = min(base_w, max(base_w * .28, width))
        height = width * 9 / 16
        return np.array([np.clip(cx - width / 2, 0, iw - width),
                         np.clip(cy - height / 2, 0, ih - height), width, height])

    anchors = [crop(iw * rng.choice([.15, .85]), ih * .3, base_w * .55),
               crop(iw / 2, ih / 2, base_w)]
    for obj in objects:
        x1, y1, x2, y2 = obj['bbox']
        anchors.append(crop((x1+x2)/2, (y1+y2)/2,
                            max((x2-x1)*2.5, (y2-y1)*16/9*2.5)))
    anchors += [crop(iw / 2, ih / 2, base_w),
                crop(iw * rng.choice([.1, .9]), ih * .8, base_w * .55)]
    for frame in range(count):
        position = frame / max(1, count-1) * (len(anchors)-1)
        index = min(int(position), len(anchors)-2)
        t = position-index
        t = t*t*t*(t*(t*6-15)+10)
        yield tuple(map(float, anchors[index]*(1-t) + anchors[index+1]*t))


def project_bbox(box, crop, output):
    x, y, cw, ch = crop
    w, h = output
    x1, y1, x2, y2 = box
    raw = [(x1-x)*w/cw, (y1-y)*h/ch, (x2-x)*w/cw, (y2-y)*h/ch]
    clipped = [max(0, min(w, raw[0])), max(0, min(h, raw[1])),
               max(0, min(w, raw[2])), max(0, min(h, raw[3]))]
    area = max(0, clipped[2]-clipped[0])*max(0, clipped[3]-clipped[1])
    fraction = area / ((raw[2]-raw[0])*(raw[3]-raw[1]))
    return {'bbox_xyxy_px': clipped if area else None,
            'bbox': [clipped[0]/w, clipped[1]/h, clipped[2]/w, clipped[3]/h] if area else None,
            'visible': area > 0, 'visible_fraction': fraction,
            'truncated': 0 < fraction < .999999,
            'quality_score': fraction * math.sqrt(area / (w*h))}


def generate(image_path, config, out_dir, progress=lambda value: None, stage=lambda text: None):
    started = time.perf_counter()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    config = validate(config, image.size)
    w, h, fps = config['width'], config['height'], config['fps']
    count = round(config['duration'] * fps)
    video = out / 'video.mp4'
    best = {}
    key_original_masks={}
    intervals = {obj['object_id']: [] for obj in config['objects']}
    renderer=None
    depth_metadata=None
    crops=list(camera_path(image.size,config['objects'],count,config['seed']))
    flight_plan=None
    flight_samples=None
    guided=bool(config['focus_points'] or config['overview'])
    if config['motion'] in ('calm','drone') or guided:
        from flight import make_flight,sample_flight,make_focus_flight
        flight_plan=(make_focus_flight(image.size,config['objects'],config['focus_points'],count/fps,config['seed'],config['motion'],overview=config['overview'])
                     if guided else make_flight(image.size,config['objects'],count/fps,config['seed'],config['motion']))
        flight_samples=sample_flight(flight_plan,image.size,count,fps)
        crops=[sample['crop_xywh'] for sample in flight_samples]
        (out/'flight_plan.json').write_text(json.dumps(flight_plan,ensure_ascii=False,indent=2),encoding='utf-8')
    poses=None
    if config['motion']=='depth':
        from depth_estimation import estimate_depth,protect_defects,save_depth,stabilize_layers
        from parallax import DepthRenderer,motion_pose
        stage('Подготовка карты глубины')
        raw,depth_metadata=estimate_depth(image,stage)
        effective,protected=protect_defects(raw,config['objects'],image.size)
        effective=stabilize_layers(effective)
        save_depth(out,raw,effective,protected,depth_metadata)
        progress(8)
        stage('Построение объёмной поверхности и проверка траектории')
        renderer=DepthRenderer(image,effective,protected,config['objects'],(w,h))
        try:
            for multiplier in (1.,.6,.3,.15,0.):
                actual=config['parallax_strength']*multiplier
                poses=[motion_pose(crop,image.size,(w,h),i/fps,count/fps,config['seed'],actual,renderer.focus_depth)
                       for i,crop in enumerate(crops)]
                if guided:
                    # Preserve exact framing at inspection holds; ease translation back in on transitions.
                    for i,pose in enumerate(poses):
                        segment=flight_plan['segments'][flight_samples[i]['segment_index']]
                        if segment['maneuver']=='focus_hold': factor=0.
                        else:
                            u=(i/fps-segment['start_s'])/(segment['end_s']-segment['start_s'])
                            factor=math.sin(math.pi*np.clip(u,0,1))**2
                        poses[i]=motion_pose(crops[i],image.size,(w,h),i/fps,count/fps,config['seed'],actual*factor,
                                             renderer.focus_depth,crop_scale=1-.14*factor)
                safe=True
                for i in np.linspace(0,count-1,min(count,31)).astype(int):
                    _,uv=renderer.draw(poses[i],read_rgb=False)
                    if not (uv[:,:,3]>.5).all():safe=False;break
                if safe:break
            if not safe:raise RuntimeError('Не удалось построить траекторию внутри исходного фото.')
            depth_metadata.update(renderer.metadata)
            depth_metadata['requested_parallax_strength']=config['parallax_strength']
            depth_metadata['actual_parallax_strength']=actual
            depth_metadata['warnings']=[]
            if multiplier<1:
                depth_metadata['warnings'].append('Амплитуда движения уменьшена, чтобы не выходить за границы исходника.')
            if actual==0:
                depth_metadata['warnings'].append('Для этого фото параллакс отключён проверкой границ. Требуется более широкий исходник.')
            (out/'depth_metadata.json').write_text(json.dumps(depth_metadata,ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception:
            renderer.close()
            raise
    stage('Рендеринг видео и покадровой разметки')
    focus_checks={}
    focus_visits=[]
    if guided:
        for segment in flight_plan['segments']:
            if segment['maneuver']=='focus_hold':
                index=min(count-1,round((segment['start_s']+segment['end_s'])/2*fps))
                focus_checks[index]=segment
    from effects import CaptureEffects
    capture=CaptureEffects(config)
    writer = imageio_ffmpeg.write_frames(str(video), (w, h), fps=fps,
        codec='libx264', pix_fmt_in='rgb24', pix_fmt_out='yuv420p',
        macro_block_size=1, output_params=['-preset', 'ultrafast', '-crf', '18', '-movflags', '+faststart'])
    try:
        writer.send(None)
        with (out / 'tracks.jsonl').open('w', encoding='utf-8') as tracks:
            for index, crop in enumerate(crops):
                x, y, cw, ch = crop
                matrix = None
                depth_items=None
                if renderer is not None:
                    frame,depth_items=renderer.render(poses[index])
                elif config['motion'] == 'classic':
                    frame = image.transform((w, h), Image.Transform.EXTENT,
                                            (x, y, x+cw, y+ch), Image.Resampling.BILINEAR)
                else:
                    matrix, inverse = drone_matrix(crop, image.size, (w,h), index/fps,
                                                   config['seed'], .4 if config['motion']=='calm' else 1.,
                                                   attitude=flight_samples[index]['attitude_rad'] if flight_samples is not None else None)
                    frame = image.transform((w,h), Image.Transform.PERSPECTIVE,
                                            tuple(inverse.flat)[:8], Image.Resampling.BILINEAR)
                frame,effect_info=capture.apply(frame,index,crop,matrix,poses[index] if poses else None)
                writer.send(np.asarray(frame))
                if index in focus_checks:
                    segment=focus_checks[index]
                    target=next(t for t in flight_plan['targets'] if t['kind']==segment['target_kind'] and t['target_id']==segment['target_id'])
                    view=project(target['bbox'],matrix,(w,h)) if matrix is not None else project_bbox(target['bbox'],crop,(w,h))
                    if view['visible_fraction']<.98:
                        raise RuntimeError(f'Не удалось полностью зафиксировать рамку «{target["label"]}». Измените рамку или выберите другой режим.')
                    focus_visits.append({'target_kind':target['kind'],'target_id':target['target_id'],'label':target['label'],
                                         'frame_index':index,'timecode_s':index/fps,'hold_start_s':segment['start_s'],
                                         'hold_end_s':segment['end_s'],'bbox':view['bbox'],'visible_fraction':view['visible_fraction']})
                annotations = []
                for object_index,obj in enumerate(config['objects']):
                    item = depth_items[object_index] if depth_items is not None else {'object_id': obj['object_id'], 'label': obj['label'],
                            **(project(obj['bbox'], matrix, (w,h)) if matrix is not None
                               else project_bbox(obj['bbox'], crop, (w, h)))}
                    annotations.append(item)
                    item['quality_score']*=1/(1+effect_info['blur_radius_px']+effect_info['noise_sigma_255']/8)
                    oid = obj['object_id']
                    if item['visible']:
                        spans = intervals[oid]
                        if spans and spans[-1][1] == index-1:
                            spans[-1][1] = index
                        else:
                            spans.append([index, index])
                        if item.get('keyframe_eligible',True) and (oid not in best or item['quality_score'] > best[oid]['quality_score']):
                            best[oid] = {**item, 'frame_index': index, 'timecode_s': index/fps}
                            if renderer is not None:
                                key_original_masks[oid]=renderer.last_original_mask.copy()
                tracks.write(json.dumps({'frame_index': index, 'timecode_s': index/fps,
                                         'capture_effects':effect_info,
                                         'crop_xywh': crop,
                                         'camera_3d':poses[index] if poses is not None else None,
                                         'flight_motion':flight_samples[index] if flight_samples is not None else None,
                                         'reconstructed_fraction':renderer.last_reconstructed_fraction if renderer is not None else 0.,
                                         'source_to_frame_matrix': matrix.tolist() if matrix is not None else None,
                                         'objects': annotations})+'\n')
                if index % max(1, fps) == 0:
                    progress(int(10+80*(index+1)/count))
    finally:
        try:
            writer.close()
        finally:
            if renderer is not None:renderer.close()
    # Decode the actual MP4: verify its frame count and dimensions, and save exact keyframes.
    stage('Проверка MP4 и извлечение ключевых кадров')
    reader = imageio_ffmpeg.read_frames(str(video), pix_fmt='rgb24')
    metadata = next(reader)
    key_dir = out / 'keyframes'
    key_dir.mkdir(exist_ok=True)
    decoded = 0
    for index, raw in enumerate(reader):
        decoded += 1
        for oid, item in best.items():
            if index == item['frame_index']:
                name = f'keyframes/object_{oid}.png'
                Image.frombytes('RGB', (w, h), raw).save(out / name)
                item['image'] = name
                if oid in key_original_masks:
                    mask_name=f'keyframes/object_{oid}_original_mask.png'
                    Image.fromarray(key_original_masks[oid].astype('uint8')*255).save(out/mask_name)
                    item['original_pixels_mask']=mask_name
    if decoded != count or tuple(metadata['size']) != (w, h):
        raise RuntimeError('Проверка выходного MP4 не пройдена.')
    result = {'schema_version': '1.2', 'synthetic': True,
        'method': 'layered_depth_parallax' if renderer is not None else ('projective_drone' if config['motion'] != 'classic' else '2d_crop_pan_zoom'),
        'depth':depth_metadata,
        'flight_plan':flight_plan,
        'focus_points':config['focus_points'],
        'focus_visits':focus_visits,
        'source_sha256': hashlib.sha256(Path(image_path).read_bytes()).hexdigest(),
        'source_size': image.size, 'coordinate_convention': 'EXIF-oriented source; bbox normalized xyxy; frame_index zero-based',
        'video': {'file': 'video.mp4', 'width': w, 'height': h, 'fps': metadata['fps'],
                  'fps_mode': 'CFR', 'frame_count': decoded, 'duration_s': decoded/metadata['fps'],
                  'container_duration_s': metadata['duration']},
        'config': config, 'keyframe_selection': 'max visible_fraction * sqrt(normalized_visible_area); depth mode requires >=95% visibility, >=16 pixels, <=1% uncertain pixels; geometric proxy penalized by capture blur and noise',
        'objects': [{**obj, 'visibility_intervals_frames_inclusive': intervals[obj['object_id']],
                     'keyframe': best.get(obj['object_id']),
                     'keyframe_warning':None if obj['object_id'] in best else 'Нет кадра с достаточной видимостью и надёжной геометрией.'} for obj in config['objects']]}
    result['generation_seconds'] = round(time.perf_counter()-started, 3)
    (out/'annotations.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    stage('Упаковка видео, глубины и разметки')
    with zipfile.ZipFile(out/'result.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for file in [video, out/'annotations.json', out/'tracks.jsonl', *key_dir.glob('*.png'), *out.glob('depth_*'), *out.glob('flight_plan.json')]:
            archive.write(file, file.relative_to(out))
    progress(100)
    return result
