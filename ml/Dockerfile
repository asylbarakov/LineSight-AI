FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STORAGE_DIR=/data

WORKDIR /app

COPY backend/requirements.txt /tmp/backend-requirements.txt
COPY ml/requirements.txt /tmp/worker-requirements.txt

RUN pip install --no-cache-dir \
    -r /tmp/backend-requirements.txt \
    -r /tmp/worker-requirements.txt

COPY backend/app/ ./app/
COPY ml/ ./

RUN groupadd --gid 10001 linesight \
    && useradd --uid 10001 --gid linesight \
    --no-create-home linesight \
    && mkdir -p /data/videos /data/frames \
    && chown -R linesight:linesight /app /data

USER linesight

CMD ["python", "-m", "worker"]
