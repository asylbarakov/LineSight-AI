FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STORAGE_DIR=/data

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY alembic.ini ./alembic.ini
COPY migrations/ ./migrations/

RUN groupadd --gid 10001 linesight \
    && useradd --uid 10001 --gid linesight --no-create-home linesight \
    && mkdir -p /data/videos /data/frames \
    && chown -R linesight:linesight /app /data
USER linesight

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
