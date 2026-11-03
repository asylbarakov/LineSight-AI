"""Интеграционные тесты API: вход, загрузка, обработка воркером, находки, решения, метрики, PDF."""

import pytest
from fastapi.testclient import TestClient

from app import repository as repo
from app.main import create_app
from app.processing import run_inspection
from ml.config import PipelineConfig


@pytest.fixture()
def client(settings):
    return TestClient(create_app(settings))


@pytest.fixture()
def auth(client):
    r = client.post("/api/login", json={"login": "admin", "password": "pw"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def upload(client, auth, path, name="flight.mp4", title="Облёт 1"):
    with open(path, "rb") as fh:
        return client.post("/api/inspections", headers=auth, files={"file": (name, fh, "video/mp4")}, data={"title": title})


def process_next(client, settings, detector=None):
    """Имитирует воркер: берёт задачу из очереди и обрабатывает её."""
    sf = client.app.state.session_factory
    with sf() as s:
        insp = repo.claim_next(s)
    assert insp is not None
    return run_inspection(sf, settings, insp.id, cfg=PipelineConfig(detector="none"), detector=detector)


@pytest.mark.parametrize("method,url", [
    ("get", "/api/inspections"), ("get", "/api/metrics"), ("patch", "/api/findings/x"),
    ("get", "/api/inspections/x/report.pdf"), ("post", "/api/inspections"),
])
def test_endpoints_require_token(client, method, url):
    assert getattr(client, method)(url).status_code == 401


def test_login_wrong_password(client):
    r = client.post("/api/login", json={"login": "admin", "password": "bad"})
    assert r.status_code == 401


def test_upload_rejects_non_mp4_and_fake_mp4(client, auth, tmp_path):
    txt = tmp_path / "a.txt"
    txt.write_text("hello")
    assert upload(client, auth, txt, name="a.txt").status_code == 415
    fake = tmp_path / "fake.mp4"
    fake.write_text("это не видео, просто текст с расширением mp4")
    r = upload(client, auth, fake, name="fake.mp4")
    assert r.status_code == 422 and r.json()["error_code"] == "E_VIDEO_INVALID"


def test_upload_too_large(client, auth, tmp_path):
    big = tmp_path / "big.mp4"
    big.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * (6 * 1024 * 1024))
    assert upload(client, auth, big, name="big.mp4").status_code == 413


def test_full_flow(client, auth, settings, blur_video):
    r = upload(client, auth, blur_video)
    assert r.status_code == 201
    iid = r.json()["id"]
    assert r.json()["status"] == "queued"

    assert client.get(f"/api/inspections/{iid}/report.pdf", headers=auth).status_code == 409  # ещё не done

    assert process_next(client, settings) is True
    detail = client.get(f"/api/inspections/{iid}", headers=auth).json()
    assert detail["status"] == "done" and detail["fps"] > 0 and "decode" in detail["stage_times"]

    findings = client.get(f"/api/inspections/{iid}/findings", headers=auth).json()
    lv = [f for f in findings if f["type"] == "low_visibility"]
    assert len(lv) == 1 and lv[0]["status"] == "new" and lv[0]["frame_path"]

    # ключевой кадр и видео отдаются
    name = lv[0]["frame_path"].split("/")[-1]
    assert client.get(f"/api/inspections/{iid}/frames/{name}", headers=auth).status_code == 200
    assert client.get(f"/api/inspections/{iid}/video", headers=auth).status_code == 200

    # решение инженера
    fid = lv[0]["id"]
    assert client.patch(f"/api/findings/{fid}", headers=auth, json={"status": "confirmed"}).json()["status"] == "confirmed"
    assert client.patch(f"/api/findings/{fid}", headers=auth, json={"status": "reshoot"}).json()["status"] == "reshoot"
    assert client.patch(f"/api/findings/{fid}", headers=auth, json={"status": "bogus"}).status_code == 422
    assert client.patch("/api/findings/unknown", headers=auth, json={"status": "confirmed"}).status_code == 404

    # PDF
    pdf = client.get(f"/api/inspections/{iid}/report.pdf", headers=auth)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # метрики
    m = client.get("/api/metrics", headers=auth).json()
    assert m["inspections_total"] == 1 and m["failed_share"] == 0 and m["avg_fps"] > 0

    # список
    lst = client.get("/api/inspections", headers=auth).json()
    assert lst[0]["findings_count"] == len(findings)


def test_reprocess_does_not_duplicate_and_keeps_decisions(client, auth, settings, blur_video):
    iid = upload(client, auth, blur_video).json()["id"]
    process_next(client, settings)
    fid = client.get(f"/api/inspections/{iid}/findings", headers=auth).json()[0]["id"]
    client.patch(f"/api/findings/{fid}", headers=auth, json={"status": "rejected"})
    n1 = len(client.get(f"/api/inspections/{iid}/findings", headers=auth).json())

    with client.app.state.session_factory() as s:
        repo.requeue(s, iid)
    process_next(client, settings)
    after = client.get(f"/api/inspections/{iid}/findings", headers=auth).json()
    assert len(after) == n1
    assert next(f for f in after if f["id"] == fid)["status"] == "rejected"


def test_failed_inspection_has_error_code(client, auth, settings, blur_video, tmp_path):
    iid = upload(client, auth, blur_video).json()["id"]
    # портим сохранённое видео: после проверки при загрузке оно стало нечитаемым
    from app import storage
    storage.video_path(settings.data_dir, iid).write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"garbage" * 100)
    assert process_next(client, settings) is False
    detail = client.get(f"/api/inspections/{iid}", headers=auth).json()
    assert detail["status"] == "failed" and detail["error_code"] in {"E_VIDEO_INVALID", "E_DECODE"}
    assert client.get(f"/api/inspections/{iid}/report.pdf", headers=auth).status_code == 409
