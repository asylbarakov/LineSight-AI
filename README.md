# LineSight AI

Система интеллектуальной инспекции ЛЭП на основе компьютерного зрения. Тестовый MVP (1–9 ноября 2026): принимает видео облёта, находит объекты и проблемные участки, инженер подтверждает находки и получает PDF-отчёт на русском.

Система не ставит диагноз и не заменяет инженера: решение всегда за человеком.

## Структура

| Папка | Что внутри |
| --- | --- |
| `backend/` | FastAPI: API, БД, хранилище, воркер (очередь в Postgres) |
| `frontend/` | Next.js + TypeScript + Tailwind, тёмная тема |
| `ml/` | Предобработка, детекция, трекинг, находки, обучение, синтетика |
| `data/` | Видео, кадры, веса, демо-данные (в git не попадает) |
| `docs/` | Архитектура и заметки |

Подробнее: [docs/architecture.md](docs/architecture.md).

## Быстрый старт

```bash
cp .env.example .env      # поменяйте ADMIN_PASSWORD и SECRET_KEY
docker compose up --build
```

Интерфейс: http://127.0.0.1:3000, API: http://127.0.0.1:8000/docs.

## Правила работы

- Ветка `main` только через PR с одним ревью, CI на каждый PR.
- Контракт API ниже меняется **только через PR**.

---

## Контракт

Единственный источник правды для фронтенда и бэкенда. Все эндпоинты, кроме `POST /api/login`, требуют заголовок `Authorization: Bearer <token>`; без него или с просроченным токеном ответ `401`.

### Статусы инспекции

`queued → processing → done | failed`

При `failed` заполняется `error_code`:

| Код | Когда |
| --- | --- |
| `E_VIDEO_INVALID` | файл не открывается как видео |
| `E_DECODE` | ошибка декодирования кадров |
| `E_MODEL` | нет весов или сбой инференса |
| `E_TIMEOUT` | превышен лимит времени задачи |

### Находка (Finding)

| Поле | Тип | Описание |
| --- | --- | --- |
| `id` | uuid | идентификатор |
| `type` | string | тип: `low_visibility` или класс объекта/дефекта |
| `priority` | `high` \| `medium` \| `low` \| `insufficient_data` | приоритет |
| `confidence` | float 0–1 | уверенность |
| `timecode_sec` | float | таймкод в секундах |
| `frame_path` | string \| null | относительный путь к ключевому кадру |
| `bbox` | `{x, y, w, h}` \| null | рамка в долях 0–1 от кадра (`x`, `y` — левый верхний угол) |
| `status` | `new` \| `confirmed` \| `rejected` \| `reshoot` | решение инженера |

### Эндпоинты

#### `POST /api/login`

```json
// запрос
{ "login": "admin", "password": "…" }
// ответ 200
{ "token": "eyJ…", "expires_in": 43200 }
// ответ 401
{ "detail": "Неверный логин или пароль" }
```

#### `POST /api/inspections` (multipart: `file`, `title`)

Ответ `201`:

```json
{ "id": "5b1f…", "title": "Облёт участка 1", "status": "queued" }
```

Ошибки: `415` (не MP4), `413` (больше `MAX_UPLOAD_MB`), `422` с `error_code: "E_VIDEO_INVALID"` (не открывается).

#### `GET /api/inspections`

```json
[
  { "id": "5b1f…", "title": "Облёт участка 1", "created_at": "2026-11-03T08:00:00Z",
    "status": "done", "findings_count": 4 }
]
```

#### `GET /api/inspections/{id}`

```json
{
  "id": "5b1f…", "title": "Облёт участка 1", "filename": "flight.mp4",
  "status": "done", "error_code": null, "error_message": null,
  "duration_sec": 42.5, "fps": 11.3,
  "stage_times": { "decode": 3.1, "detect": 18.4, "track": 0.6, "findings": 0.1, "db": 0.2 },
  "created_at": "…", "started_at": "…", "finished_at": "…"
}
```

#### `GET /api/inspections/{id}/video`

Видео с поддержкой `Range`. Ключевые кадры: `GET /api/inspections/{id}/frames/{name}`.

#### `GET /api/inspections/{id}/findings`

Сортировка: приоритет (`high` → `insufficient_data`), затем таймкод.

```json
[
  { "id": "9c2e…", "type": "low_visibility", "priority": "insufficient_data",
    "confidence": 0.82, "timecode_sec": 12.0, "frame_path": "frames/lv_1.jpg",
    "bbox": null, "status": "new" },
  { "id": "a7d0…", "type": "insulator", "priority": "medium",
    "confidence": 0.91, "timecode_sec": 20.5, "frame_path": "frames/t3.jpg",
    "bbox": { "x": 0.41, "y": 0.22, "w": 0.1, "h": 0.18 }, "status": "new" }
]
```

#### `PATCH /api/findings/{id}`

```json
// запрос
{ "status": "confirmed" }   // confirmed | rejected | reshoot
// ответ 200 — находка целиком; 404 — нет такого id; 422 — недопустимый статус
```

#### `GET /api/inspections/{id}/report.pdf`

PDF на русском. `409`, если инспекция ещё не `done`.

#### `GET /api/metrics`

```json
{
  "inspections_total": 7, "avg_processing_sec": 41.2, "avg_fps": 10.8, "failed_share": 0.14,
  "recent_runs": [
    { "id": "5b1f…", "title": "…", "status": "done", "fps": 11.3,
      "stage_times": { "decode": 3.1, "detect": 18.4 } }
  ]
}
```

---

## Решение Go/No-Go (задача 3)

- **Класс для детекции и трекинга:** все классы подмножества «transmission line object detection» датасета sxiong (оборудование и дефекты ЛЭП, разметка рамками). Редкие классы (меньше 20 примеров) отбрасываются на подготовке датасета.
- **Подстанция (18 классов, маски):** не берём в MVP, возможное расширение после приёмки.
- **Обучение:** запускает тимлид в Colab/Kaggle или на локальной GPU по ноутбуку `ml/notebooks/train_colab.ipynb`; готовые `best.pt` и `metrics.json` кладутся в `data/weights/`. Пока весов нет, воркер находит только «недостаточную видимость».
- **Порог 70%:** доля кадров, где объект найден верно, считается на 20–30 размеченных кадрах (`ml/check_detector.py`, `ml/evaluate.py`); итог записать сюда после первого обучения.

## Данные

Лицензии и вердикты по датасетам заполняются в задаче 29 (раздел будет дополняться).

| Датасет | Лицензия | Вердикт |
| --- | --- | --- |
| [sxiong/Power-equipment-image-dataset](https://huggingface.co/datasets/sxiong/Power-equipment-image-dataset) (~23.6 тыс. строк, ~20.7 ГБ: подстанция 18 классов с масками, ЛЭП 27–28 классов дефектов с рамками, ~3000 дрон-снимков) | MIT | можно: дообучение и показ в демо |
