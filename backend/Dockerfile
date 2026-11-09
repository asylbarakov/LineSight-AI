# Контекст сборки — корень репозитория (нужны backend/ и ml/).
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/srv

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY backend/requirements.txt backend/requirements.txt
COPY backend/requirements.lock.txt backend/requirements.lock.txt
RUN pip install --no-cache-dir -r backend/requirements.lock.txt
COPY ml/requirements-train.txt ml/requirements-train.txt
COPY backend/requirements-yolo.lock.txt backend/requirements-yolo.lock.txt
COPY backend/requirements-torch.lock.txt backend/requirements-torch.lock.txt
ARG INSTALL_YOLO=0
# YOLO нужен только воркеру; для api-образа можно собрать с --build-arg INSTALL_YOLO=0
# CPU-сборка PyTorch (~200 МБ) вместо стандартной с CUDA (несколько ГБ): так образ с YOLO собирается в разы быстрее.
# Для GPU в контейнере соберите с --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu124 (и NVIDIA Container Toolkit).
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
RUN if [ "$INSTALL_YOLO" = "1" ]; then \
      pip install --no-cache-dir -c backend/requirements.lock.txt -c backend/requirements-yolo.lock.txt \
        -r backend/requirements-torch.lock.txt --index-url "$TORCH_INDEX" \
      && pip install --no-cache-dir -c backend/requirements.lock.txt -c backend/requirements-torch.lock.txt \
        -r backend/requirements-yolo.lock.txt; \
    fi
# ultralytics тянет opencv-python (с GUI-библиотеками: libxcb, libGL), которого нет в slim-образе, и затирает
# каталог cv2 от headless-сборки. Возвращаем headless, иначе `import cv2` падает с libxcb.so.1.
RUN pip uninstall -y opencv-python opencv-contrib-python 2>/dev/null || true; \
    pip install --no-cache-dir --force-reinstall --no-deps -c backend/requirements.lock.txt opencv-python-headless \
    && python -c "import cv2; print('cv2', cv2.__version__)"

# ByteTrack otherwise tries to install lap while processing the first inspection.
# Resolve and validate tracking dependencies at build time, without model weights.
RUN if [ "$INSTALL_YOLO" = "1" ]; then \
      YOLO_AUTOINSTALL=false python -c "from ultralytics.trackers.byte_tracker import BYTETracker"; \
    fi

COPY backend backend
COPY ml ml
WORKDIR /srv/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
