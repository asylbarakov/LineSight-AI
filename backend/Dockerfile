# Контекст сборки — корень репозитория (нужны backend/ и ml/).
FROM python:3.12-slim

ARG INSTALL_YOLO=1
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/srv

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY ml/requirements-train.txt ml/requirements-train.txt
# YOLO нужен только воркеру; для api-образа можно собрать с --build-arg INSTALL_YOLO=0
RUN if [ "$INSTALL_YOLO" = "1" ]; then pip install --no-cache-dir ultralytics; fi

COPY backend backend
COPY ml ml
WORKDIR /srv/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
