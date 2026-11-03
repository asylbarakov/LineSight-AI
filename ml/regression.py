"""Регрессионный прогон на демо-наборе (задача 64).

Прогоняет видео из `ground_truth.json`, сравнивает с эталоном, пишет таблицу в `<demo>/regression.md`
и возвращает код 1, если метрика просела ниже базовой линии (`regression_baseline.json`) больше чем на 0.05
или (при отсутствии базовой линии) ниже порога: recall ≥ 0.8 для «недостаточной видимости».

    python -m ml.regression data/demo [--detector synthetic|yolo|none] [--save-baseline]
    python -m ml.regression data/demo --api http://127.0.0.1:8000 --login admin --password …   # через HTTP API
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
import uuid
from pathlib import Path

from .evaluate import TOLERANCE_SEC, compare, format_table, run_local

DROP = 0.05
MIN_LV_RECALL = 0.8


def run_api(base: str, login: str, password: str, demo: Path, truth: dict, timeout: float = 600) -> dict[str, list[dict]]:
    """Загружает каждое видео через API, ждёт `done` и забирает находки."""

    def call(method: str, path: str, token: str | None = None, data: bytes | None = None, headers: dict | None = None):
        req = urllib.request.Request(base + path, data=data, method=method, headers=headers or {})
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))

    token = call("POST", "/api/login", data=json.dumps({"login": login, "password": password}).encode(),
                 headers={"Content-Type": "application/json"})["token"]
    out: dict[str, list[dict]] = {}
    for name in truth["videos"]:
        video = demo / name
        if not video.is_file():
            continue
        boundary = uuid.uuid4().hex
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\nregression {name}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: video/mp4\r\n\r\n"
        ).encode() + video.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        iid = call("POST", "/api/inspections", token, body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})["id"]
        deadline = time.time() + timeout
        while True:
            st = call("GET", f"/api/inspections/{iid}", token)
            if st["status"] in ("done", "failed"):
                break
            if time.time() > deadline:
                raise TimeoutError(f"{name}: обработка не завершилась за {timeout} с")
            time.sleep(2)
        if st["status"] == "failed":
            raise RuntimeError(f"{name}: {st['error_code']} {st.get('error_message')}")
        out[name] = call("GET", f"/api/inspections/{iid}/findings", token)
    return out


def summarize(rows: dict) -> dict[str, dict[str, float]]:
    return {v: {k: round(s.recall, 3) for k, s in sc.items()} | {f"{k}_precision": round(s.precision, 3) for k, s in sc.items()}
            for v, sc in rows.items()}


def check(current: dict, baseline: dict | None) -> list[str]:
    """Возвращает список нарушений (пусто — всё хорошо)."""
    problems = []
    for video, metrics in current.items():
        if baseline and video in baseline:
            for k, v in metrics.items():
                if v < baseline[video].get(k, 0) - DROP:
                    problems.append(f"{video}: {k} {v:.2f} < базовой {baseline[video][k]:.2f}")
        elif metrics.get("low_visibility", 1.0) < MIN_LV_RECALL:
            problems.append(f"{video}: recall «недостаточной видимости» {metrics['low_visibility']:.2f} < {MIN_LV_RECALL}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("demo_dir")
    ap.add_argument("--detector", default="synthetic")
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("--api")
    ap.add_argument("--login", default="admin")
    ap.add_argument("--password", default="")
    a = ap.parse_args()
    demo = Path(a.demo_dir)
    truth = json.loads((demo / "ground_truth.json").read_text(encoding="utf-8"))
    tol = truth.get("tolerance_sec", TOLERANCE_SEC)
    found = run_api(a.api, a.login, a.password, demo, truth) if a.api else run_local(demo, truth, a.detector, Path("data/eval"))
    rows = {v: compare(truth["videos"][v]["expected"], f, tol) for v, f in found.items()}
    table = format_table(rows)
    current = summarize(rows)
    base_path = demo / "regression_baseline.json"
    baseline = json.loads(base_path.read_text(encoding="utf-8")) if base_path.is_file() else None
    problems = check(current, baseline)
    report = "# Регрессионный прогон\n\n" + table + "\n\n" + ("**Просадки:**\n" + "\n".join(f"- {p}" for p in problems) if problems else "Просадок нет.") + "\n"
    (demo / "regression.md").write_text(report, encoding="utf-8")
    if a.save_baseline:
        base_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
