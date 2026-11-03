"""Генератор синтетических видео облёта ЛЭП (задачи 58–59).

Сцена: небо, земля, провода, опоры с траверсой и изоляторами; камера плавно движется
вдоль линии. На заданных интервалах видео размывается или затемняется. Рядом с MP4 пишется
JSON с эталоном: интервалы плохой видимости и интервалы появления объектов в кадре.

Запуск:  python -m ml.make_synthetic --out data/demo
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

# цвета (BGR) — по ним синтетический детектор находит объекты
TOWER_BGR = (30, 60, 120)
INSULATOR_BGR = (220, 200, 40)
SKY_TOP = (235, 200, 140)
SKY_BOTTOM = (250, 225, 190)
GROUND_BGR = (70, 120, 80)
WIRE_BGR = (70, 70, 70)

WIDTH, HEIGHT = 960, 540
PAN_PX_PER_SEC = 16.0  # медленный пролёт, чтобы объект перекрывался между сэмплами кадров
POLE_X_WORLD = (300, 720, 1140, 1560)
HORIZON_Y = 400
POLE_W = 20
POLE_TOP = 120
CROSSARM = (130, 18)  # ширина, высота
INSULATOR = (24, 44)  # ширина, высота
INSULATOR_DX = (-45, 45)


def _background() -> np.ndarray:
    img = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    for y in range(HORIZON_Y):
        a = y / HORIZON_Y
        img[y, :] = [int(SKY_TOP[i] * (1 - a) + SKY_BOTTOM[i] * a) for i in range(3)]
    img[HORIZON_Y:, :] = GROUND_BGR
    return img


def _draw_frame(bg: np.ndarray, t: float, rng: np.random.Generator) -> np.ndarray:
    img = bg.copy()
    offset = PAN_PX_PER_SEC * t
    sway = int(round(4 * math.sin(t * 0.9)))  # лёгкое покачивание камеры
    xs = [int(round(xw - offset)) for xw in POLE_X_WORLD]
    # провода между опорами (провисающая линия) — рисуем первыми, опоры перекрывают их
    for a, b in zip(xs, xs[1:]):
        for dx in INSULATOR_DX:
            pts = []
            for k in range(0, 41):
                u = k / 40
                px = int(a + dx + (b - a) * u)
                py = int(POLE_TOP + CROSSARM[1] + INSULATOR[1] + sway + 30 * math.sin(math.pi * u))
                pts.append((px, py))
            cv2.polylines(img, [np.array(pts, np.int32)], False, WIRE_BGR, 2, cv2.LINE_AA)
    for cx in xs:
        # опора
        cv2.rectangle(img, (cx - POLE_W // 2, POLE_TOP + sway), (cx + POLE_W // 2, HORIZON_Y + 20), TOWER_BGR, -1)
        # траверса
        cv2.rectangle(
            img,
            (cx - CROSSARM[0] // 2, POLE_TOP + sway),
            (cx + CROSSARM[0] // 2, POLE_TOP + CROSSARM[1] + sway),
            TOWER_BGR,
            -1,
        )
        # изоляторы под траверсой
        for dx in INSULATOR_DX:
            x0 = cx + dx - INSULATOR[0] // 2
            y0 = POLE_TOP + CROSSARM[1] + sway
            cv2.rectangle(img, (x0, y0), (x0 + INSULATOR[0], y0 + INSULATOR[1]), INSULATOR_BGR, -1)
    # текстура: шум (нужен, чтобы резкость кадра была измерима)
    noise = rng.normal(0, 5, img.shape)
    return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def _interval_hit(t: float, intervals: list[tuple[float, float]]) -> bool:
    return any(a <= t < b for a, b in intervals)


def _object_intervals(duration: float) -> list[dict]:
    """Когда каждый объект виден в кадре (для эталона)."""
    result = []
    for xw in POLE_X_WORLD:
        for cls, half in (("tower", max(POLE_W, CROSSARM[0]) / 2),):
            visible = _visible_interval(xw, half, duration)
            if visible:
                result.append({"class": cls, "first_sec": visible[0], "last_sec": visible[1]})
        for dx in INSULATOR_DX:
            visible = _visible_interval(xw + dx, INSULATOR[0] / 2, duration)
            if visible:
                result.append({"class": "insulator", "first_sec": visible[0], "last_sec": visible[1]})
    return result


def _visible_interval(x_world: float, half_w: float, duration: float) -> tuple[float, float] | None:
    # объект виден, пока его экранный диапазон пересекается с [0, WIDTH]
    t_in = (x_world - half_w - WIDTH) / PAN_PX_PER_SEC  # правый край входит в кадр
    t_out = (x_world + half_w) / PAN_PX_PER_SEC  # левый край выходит
    start, end = max(0.0, t_in), min(duration, t_out)
    if end <= start:
        return None
    return (round(start, 2), round(end, 2))


def make_video(
    out_path: str | Path,
    duration: float = 26.0,
    fps: int = 10,
    blur: list[tuple[float, float]] | None = None,
    dark: list[tuple[float, float]] | None = None,
    seed: int = 0,
) -> dict:
    """Создаёт MP4 (H.264, если есть ffmpeg) и JSON-эталон рядом. Возвращает эталон."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blur = blur or []
    dark = dark or []
    rng = np.random.default_rng(seed)
    bg = _background()

    tmp = Path(tempfile.mkdtemp(prefix="synth_")) / "raw.mp4"
    writer = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError("OpenCV не смог открыть VideoWriter")
    n = int(duration * fps)
    for i in range(n):
        t = i / fps
        frame = _draw_frame(bg, t, rng)
        if _interval_hit(t, blur):
            frame = cv2.GaussianBlur(frame, (0, 0), sigmaX=9)
        if _interval_hit(t, dark):
            frame = (frame.astype(np.float32) * 0.2).astype(np.uint8)
        writer.write(frame)
    writer.release()

    if shutil.which("ffmpeg"):
        # браузеры не играют mp4v — перекодируем в H.264
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-preset", "veryfast", "-crf", "20", "-movflags", "+faststart", str(out_path)],
            check=True,
        )
    else:
        shutil.copy(tmp, out_path)
    shutil.rmtree(tmp.parent, ignore_errors=True)

    truth = {
        "video": out_path.name,
        "fps": fps,
        "duration_sec": duration,
        "width": WIDTH,
        "height": HEIGHT,
        "low_visibility": [{"start_sec": a, "end_sec": b, "kind": "blur"} for a, b in blur]
        + [{"start_sec": a, "end_sec": b, "kind": "dark"} for a, b in dark],
        "objects": _object_intervals(duration),
    }
    out_path.with_suffix(".json").write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    return truth


PRESETS = {
    "synth_clean": dict(blur=[], dark=[], seed=1),  # ролик 1: чистый
    "synth_blur": dict(blur=[(9.0, 16.0)], dark=[], seed=2),  # ролик 2: размытый участок 7 с
    "synth_dark": dict(blur=[], dark=[(10.0, 16.0)], seed=3),  # ролик 3: тёмный участок 6 с
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/demo", help="папка для видео и эталонов")
    ap.add_argument("--duration", type=float, default=26.0)
    ap.add_argument("--fps", type=int, default=10)
    args = ap.parse_args()
    for name, params in PRESETS.items():
        path = Path(args.out) / f"{name}.mp4"
        truth = make_video(path, duration=args.duration, fps=args.fps, **params)
        print(f"{path}: плохих участков {len(truth['low_visibility'])}, объектов {len(truth['objects'])}")


if __name__ == "__main__":
    main()
