# локальный запуск

## Требования

- Git
- Docker Engine или Docker Desktop
- Docker Compose v2
- Свободные порты 3000 и 8000

Все команды выполняются из корня репозитория. В Linux при необходимости используйте `sudo` перед `docker`.

## 1. Подготовка

```bash
git clone https://github.com/asylbarakov/LineSight-AI.git
cd LineSight-AI

cp .env.example .env
```
Нужно зайти на свой гит, можно пропустить и скачать архив с гитхаба

В файле `.env` обязательно измените `POSTGRES_PASSWORD`. При необходимости измените `WEB_PORT` и `API_PORT`.

Файл `.env` не должен попадать в Git.

## 2. Первый запуск

Проверка конфигурации:

```bash
docker compose --env-file .env -f infra/compose.yaml config --quiet
```

Запуск PostgreSQL и API:

```bash
docker compose --env-file .env -f infra/compose.yaml up -d --build postgres api
```

Применение миграций:

```bash
docker compose --env-file .env -f infra/compose.yaml run --rm api alembic upgrade head
```

Запуск остальных сервисов:

```bash
docker compose --env-file .env -f infra/compose.yaml up -d --build worker web
```

Проверка контейнеров:

```bash
docker compose --env-file .env -f infra/compose.yaml ps
```

## 3. Проверка

| Адрес | Назначение |
|---|---|
| http://127.0.0.1:3000 | Frontend |
| http://127.0.0.1:8000/docs | Swagger API |
| http://127.0.0.1:8000/health | Проверка API, БД и хранилища |
| http://127.0.0.1:3000/api/health | Проверка связи frontend с API |

Проверка версии БД:

```bash
docker compose --env-file .env -f infra/compose.yaml run --rm api alembic current
```

Ожидаемая версия:

```text
0002_job_runtime (head)
```

При изменении моделей БД применяйте новые миграции через `alembic upgrade head`.

## 4. Повседневная работа

Запуск существующих контейнеров:

```bash
docker compose --env-file .env -f infra/compose.yaml up -d
```

Пересборка после изменения кода:

```bash
docker compose --env-file .env -f infra/compose.yaml up -d --build
```

Просмотр логов:

```bash
docker compose --env-file .env -f infra/compose.yaml logs -f --tail=100
```

Остановка:

```bash
docker compose --env-file .env -f infra/compose.yaml down
```

Данные PostgreSQL и загруженные видео хранятся в Docker volumes и сохраняются после `down`.

**Не пиши `down -v`, если необходимо сохранить данные.**

## 5. Troubleshooting

| Проблема | Решение |
|---|---|
| `Cannot connect to Docker daemon` | Запустить Docker Engine/Desktop, проверить права доступа |
| Ошибка `POSTGRES_PASSWORD` | Проверить наличие `.env` и значение пароля |
| PostgreSQL `unhealthy` | Проверить `docker compose ... logs postgres` |
| `relation ... does not exist` | Выполнить `alembic upgrade head` |
| `port is already allocated` | Изменить `WEB_PORT` или `API_PORT` в `.env` |
| API возвращает `503` | Проверить PostgreSQL, доступность `/data` и логи API |
| Ошибки записи в `/data` | Проверить права на Docker volume `media_data` |
| Worker не обрабатывает задания | Проверить настройку ML-процессора и логи worker |

**Важно:** изменение `POSTGRES_PASSWORD` после первой инициализации volume не изменяет пароль существующего пользователя PostgreSQL автоматически. Не удаляйте volume для исправления проблемы без резервной копии.

### ML worker

В базовой конфигурации `ml/processor.py` содержит `READY = False`. Поэтому worker запускается, но не забирает задания из очереди.

Это ожидаемое поведение до подключения ML-модели. Загруженные видео остаются в статусе `queued`.

### Диагностика

Для просмотра логов отдельного сервиса:

```bash
docker compose --env-file .env -f infra/compose.yaml logs --tail=100 api
docker compose --env-file .env -f infra/compose.yaml logs --tail=100 postgres
docker compose --env-file .env -f infra/compose.yaml logs --tail=100 worker
```

При ошибках сборки проверьте подключение к интернету и полный вывод `docker compose build`.

## 6. Структура

- `frontend/` — Next.js
- `backend/` — FastAPI, SQLAlchemy, Alembic
- `ml/` — worker и интерфейс ML-модели
- `infra/compose.yaml` — конфигурация сервисов
- `docs/architecture.md` — архитектура системы

Доступ к PostgreSQL и общему хранилищу осуществляется внутри Docker-сети. Порты web и API по умолчанию доступны только на `127.0.0.1`.
