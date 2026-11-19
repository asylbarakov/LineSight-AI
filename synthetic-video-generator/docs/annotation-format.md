# Формат результатов LineSight Synth

Текущая схема: `schema_version: "1.2"`. Дополнительные поля могут появляться;
читатели должны игнорировать неизвестные поля. Видео синтетическое, разметка
переносится геометрически из фото, а не вычисляется детектором.

## Файлы

Результат лежит в `output/<job_id>/`; ZIP содержит MP4, разметку и ключевые кадры.
Исходное нормализованное фото source.png остаётся локально и не включается в ZIP.

| Файл | Назначение |
|---|---|
| video.mp4 | H.264, CFR, без нарисованных рамок |
| annotations.json | Паспорт видео, исходные рамки, интервалы видимости, лучшие кадры |
| tracks.jsonl | Один самостоятельный JSON на строку, одна строка на кадр |
| flight_plan.json | План камеры, если выбран режим с планировщиком; также вложен в annotations |
| keyframes/object_N.png | Лучший кадр объекта N, извлечённый из готового MP4 |
| depth_* | Карты и параметры глубины, только в режиме параллакса |

Пути внутри метаданных относительны корню распакованного ZIP.

## Координаты — важное различие

Все bbox имеют порядок `[xmin, ymin, xmax, ymax]`, НЕ `[x,y,width,height]`
и НЕ YOLO `[center_x,center_y,width,height]`. Начало координат сверху слева,
X вправо, Y вниз. Исходник ориентирован по EXIF. Импорт VOC сохраняет координаты
без сдвига −1; размеры XML должны совпадать с ориентированным изображением.

| Путь поля | Единицы |
|---|---|
| annotations.objects[].bbox | Пиксели исходного фото |
| annotations.config.objects[].bbox | Пиксели исходного фото |
| annotations.focus_points[].bbox | Пиксели исходного фото |
| flight_plan.targets[].bbox | Пиксели исходного фото |
| tracks.objects[].bbox | Нормализованный xyxy текущего видеокадра, 0–1 |
| tracks.objects[].bbox_xyxy_px | Пиксели текущего видеокадра |
| annotations.objects[].keyframe.bbox | Нормализованный xyxy ключевого кадра |
| annotations.objects[].keyframe.bbox_xyxy_px | Пиксели ключевого кадра |
| annotations.focus_visits[].bbox | Нормализованный xyxy контрольного кадра |

Имя bbox перегружено; общее coordinate_convention не отменяет различий этой таблицы.
Пиксельные координаты могут быть дробными; границы лежат в [0,width] и [0,height].
В масках depth правая и нижняя границы bbox исключающие (последний пиксель + 1).
Нормализация: `[xmin/W, ymin/H, xmax/W, ymax/H]`.

## annotations.json

- `video`: file, width, height, fps, fps_mode=CFR, frame_count, duration_s,
  container_duration_s. MP4 полностью декодируется для проверки количества и размеров.
  duration_s = frame_count / fps; container_duration_s сообщает контейнер.
- `source_size`: [W,H]; `source_sha256`: SHA256 файла, переданного генератору
  (в UI это нормализованный source.png, не байты оригинального JPEG).
- `method`: 2d_crop_pan_zoom, projective_drone или layered_depth_parallax.
- `config`: принятые настройки, seed, исходные дефекты и точки.
- `objects`: object_id (начиная с 1, уникален внутри видео), label, исходный bbox,
  visibility_intervals_frames_inclusive, keyframe, keyframe_warning.
- `keyframe`: копия покадровой разметки плюс frame_index, timecode_s, image;
  может быть null, если подходящего кадра нет.
- `visibility_intervals_frames_inclusive`: например [[52,121],[200,230]];
  обе границы включены, достаточно видимости части размеченной области.
- `focus_points`: дополнительные пользовательские рамки, не классы дефектов.
- `focus_visits`: контроль в середине фиксации: target_kind, target_id, label,
  frame_index, timecode_s, hold_start_s, hold_end_s, bbox, visible_fraction.
- `flight_plan`: копия плана или null; `depth`: параметры глубины или null.
- `generation_seconds`: генерация и проверка, без времени упаковки ZIP.

target_kind=defect ссылается на object_id, context — на point_id.
overview обозначает автоматически добавленный общий план. Идентификаторы разных
типов могут совпадать. Контрольный кадр посещения не равен лучшему кадру дефекта.
Дополнительные точки и общий план не добавляются в tracks.objects.

## tracks.jsonl

Нумерация кадров с нуля; timecode_s = frame_index / fps. Все объекты присутствуют
на каждой строке, включая невидимые. Поэтому проверяйте visible и bbox, а не только
наличие объекта. Пример сокращённой строки (условные числа):

```json
{"frame_index":75,"timecode_s":5.0,"objects":[{"object_id":1,"label":"defect","bbox":[0.25,0.2,0.75,0.8],"bbox_xyxy_px":[160,72,480,288],"visible":true,"visible_fraction":1.0,"truncated":false,"quality_score":0.5477}]}
```

При полном исчезновении: visible=false, bbox=null, bbox_xyxy_px=null,
visible_fraction=0. Не заменяйте null рамкой из соседнего кадра.

Верхний уровень строки:

- crop_xywh: окно исходника [x,y,width,height], пиксели;
- source_to_frame_matrix: гомография 3×3 для проективных режимов, иначе null;
- flight_motion: crop_xywh, attitude_rad=[yaw,pitch,roll], segment_index, maneuver;
- camera_3d: eye, rotation, intrinsics, crop_xywh в depth, иначе null;
- reconstructed_fraction: доля восстановленных пикселей кадра;
- capture_effects: blur_radius_px, noise_sigma_255, motion_activity (0–1).

У каждого объекта bbox охватывает видимую часть преобразованной исходной рамки.
visible_fraction — геометрическая доля видимости области, не confidence детектора.
quality_score — рейтинг для выбора кадра, тоже не confidence.

## Как переносится bbox

**Классический режим:** из координат вычитается начало crop, затем применяется
масштаб W/crop_width и H/crop_height. Рамка обрезается границами кадра.

**Дрон и спокойный подвес:** той же матрицей, что и фото, преобразуются четыре угла
bbox. polygon_xy_px — получившийся четырёхугольник (может выходить за кадр),
visible_polygon_xy_px — его обрезанная часть. Вокруг неё строится осевой bbox.
visible_fraction определяется по площади полигона, а не охватывающего прямоугольника.
truncated=true при частичной обрезке; при полном исчезновении здесь false.

**Глубина:** renderer хранит происхождение пикселей и учитывает перекрытие слоёв.
Рамка охватывает только видимые исходные пиксели из исходного bbox. Восстановленный
фон не создаёт разметку. visible_pixels — их число; occluded_fraction — доля
перекрытия относительно изолированного прохода в кадре; uncertain_fraction — доля
геометрически неопределённых видимых пикселей. projected_source_bbox_polygon хранит
проекцию углов. truncated проверяет выход углов за границы, включая полное исчезновение.
visible_fraction учитывает обрезку и перекрытие; это растровая оценка.

Разметка прямоугольная, не сегментационная: фон внутри исходного bbox относится
к размеченной области. Ошибки исходной рамки сохраняются. Точность относительно
рендера не означает достоверную 3D-реконструкцию настоящего объекта.

## Ключевые кадры и эффекты

Геометрический рейтинг: visible_fraction × sqrt(видимая площадь / площадь кадра).
В глубине площадь измеряется видимыми пикселями; допускаются кадры с видимостью
≥95%, ≥16 пикселями, uncertain_fraction≤1%. Допуск отмечен keyframe_eligible.
Рейтинг делится на `1 + blur_radius_px + noise_sigma_255 / 8`.
Максимум выбирается отдельно для каждого дефекта; при равенстве берётся первый кадр.
Это эвристика, не оценка резкости нейросетью.

Шум и размытие применяются после геометрии. Bbox не расширяется на ореол смаза,
visible_fraction не измеряет распознаваемость после размытия. original_pixels_mask
ключевого кадра глубины описывает происхождение до эффектов и видеосжатия.

## flight_plan.json

version, seed, profile, duration_s задают тип маршрута. times_s — времена опорных
состояний, states — их значения, velocities — производные по секундам.
state_axes: center_x_px, center_y_px, log_crop_width_px, yaw_rad, pitch_rad, roll_rad.
Ширина хранится как натуральный логарифм. segments задаёт манёвры и интервалы;
targets, hold_seconds есть у маршрута с фиксациями. warnings содержит ограничения.
Для обучения используйте готовые tracks, не восстанавливайте bbox из плана.

## Чтение для обучения / оценки

```python
import json
from pathlib import Path

root = Path("path/to/unpacked/result")
meta = json.loads((root / "annotations.json").read_text(encoding="utf-8"))
with (root / "tracks.jsonl").open(encoding="utf-8") as stream:
    for line in stream:
        frame = json.loads(line)
        for obj in frame["objects"]:
            if not obj["visible"] or obj["bbox"] is None:
                continue
            xmin, ymin, xmax, ymax = obj["bbox"]
            yolo_box = [(xmin+xmax)/2, (ymin+ymax)/2, xmax-xmin, ymax-ymin]
            # label -> class_id задаётся общей таблицей классов команды.
            # frame_index идентифицирует кадр в video.mp4.
```

Не делите варианты одного исходного фото между train и test: сохраняйте их в одной
выборке, используя source_sha256 или общий идентификатор исходной сцены.
