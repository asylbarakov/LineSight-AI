"""Проверка GPU для PyTorch и YOLO (задача 41). Запуск: `python -m ml.check_gpu [weights.pt]`.

Ловит типичную проблему новых видеокарт (в т. ч. RTX 5060, архитектура Blackwell sm_120): сборка PyTorch
без нужных ядер даёт «no kernel image is available». Для таких карт нужен PyTorch, собранный под CUDA 12.8+.
"""

from __future__ import annotations

import sys
import time


def main() -> int:
    try:
        import torch
    except Exception as exc:  # noqa: BLE001
        print(f"PyTorch не установлен: {exc}")
        return 2
    print(f"PyTorch {torch.__version__}, CUDA сборки: {torch.version.cuda}")
    if not torch.cuda.is_available():
        print("CUDA недоступна: инференс и обучение пойдут на CPU (или используйте Colab/Kaggle).")
        return 1
    name = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    print(f"GPU: {name}, compute capability sm_{cap[0]}{cap[1]}; ядра в сборке: {torch.cuda.get_arch_list()}")
    try:
        x = torch.randn(1024, 1024, device="cuda")
        (x @ x).sum().item()
        print("Проверочная операция на GPU выполнена.")
    except Exception as exc:  # noqa: BLE001
        print(f"Операция на GPU не удалась: {exc}\n"
              "Установите PyTorch под вашу CUDA (для RTX 50xx — CUDA 12.8+, см. pytorch.org/get-started) "
              "или переходите на Colab/Kaggle.")
        return 1
    weights = sys.argv[1] if len(sys.argv) > 1 else "yolov8n.pt"
    try:
        import numpy as np
        from ultralytics import YOLO

        model = YOLO(weights)
        img = np.zeros((640, 640, 3), dtype=np.uint8)
        model.predict(img, device=0, verbose=False)  # прогрев
        t = time.perf_counter()
        n = 30
        for _ in range(n):
            model.predict(img, device=0, verbose=False)
        print(f"YOLO ({weights}) на GPU: {n / (time.perf_counter() - t):.1f} кадр/с на 640×640")
    except Exception as exc:  # noqa: BLE001
        print(f"Проверка YOLO не удалась: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
