FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STORAGE_DIR=/data

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY worker.py ./worker.py

RUN groupadd --gid 10001 linesight \
    && useradd --uid 10001 --gid linesight --no-create-home linesight \
    && mkdir -p /data/videos /data/frames \
    && chown -R linesight:linesight /app /data
USER linesight

CMD ["python", "-m", "worker"]
