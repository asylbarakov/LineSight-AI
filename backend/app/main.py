"""HTTP API LineSight AI (FastAPI). Контракт — в README, раздел «Контракт».

Запуск: `uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000`

НЕ ПРОВЕРЕНО в песочнице разработки (там нет FastAPI/SQLAlchemy): запустите `pytest backend/tests`.
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ml.errors import E_VIDEO_INVALID, PipelineError
from ml.preprocess import probe_video

from . import repository as repo
from . import security, storage
from .config import Settings
from .db import Finding, Inspection, STATUS_DONE, init_db, make_engine, make_session_factory, new_id

log = logging.getLogger("linesight.api")

COOKIE_NAME = "ls_token"
bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    login: str
    password: str


class FindingPatch(BaseModel):
    status: Literal["confirmed", "rejected", "reshoot"]


def api_error(status_code: int, detail: str, error_code: str | None = None) -> JSONResponse:
    body: dict = {"detail": detail}
    if error_code:
        body["error_code"] = error_code
    return JSONResponse(status_code=status_code, content=body)


class HTTPAuthError(Exception):
    pass


# ---------- сериализация ----------

def _iso(dt) -> str | None:
    dt = repo.aware(dt)
    return dt.isoformat() if dt else None


def finding_out(f: Finding) -> dict:
    bbox = None
    if f.bbox_x is not None:
        bbox = {"x": f.bbox_x, "y": f.bbox_y, "w": f.bbox_w, "h": f.bbox_h}
    return {
        "id": f.id,
        "type": f.type,
        "priority": f.priority,
        "confidence": f.confidence,
        "timecode_sec": f.timecode_sec,
        "frame_path": f.frame_path,
        "bbox": bbox,
        "status": f.status,
    }


def inspection_summary(i: Inspection, findings_count: int) -> dict:
    return {
        "id": i.id,
        "title": i.title,
        "created_at": _iso(i.created_at),
        "status": i.status,
        "findings_count": findings_count,
    }


def inspection_detail(i: Inspection) -> dict:
    return {
        "id": i.id,
        "title": i.title,
        "filename": i.filename,
        "status": i.status,
        "error_code": i.error_code,
        "error_message": i.error_message,
        "progress": i.progress,
        "duration_sec": i.duration_sec,
        "fps": i.fps,
        "stage_times": i.stage_times,
        "created_at": _iso(i.created_at),
        "started_at": _iso(i.started_at),
        "finished_at": _iso(i.finished_at),
    }


# ---------- приложение ----------

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    engine = make_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)

    app = FastAPI(title="LineSight AI", version="0.1.0")
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.engine = engine

    def get_session(request: Request):
        with request.app.state.session_factory() as session:
            yield session

    def require_admin(request: Request, creds=Depends(bearer)) -> None:
        token = creds.credentials if creds else request.cookies.get(COOKIE_NAME)
        if not token or not security.verify_token(settings, token):
            raise HTTPAuthError()

    @app.exception_handler(HTTPAuthError)
    async def _auth_handler(_request: Request, _exc: HTTPAuthError):
        return JSONResponse(
            status_code=401, content={"detail": "Требуется вход"}, headers={"WWW-Authenticate": "Bearer"}
        )

    # ----- служебные -----

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # ----- вход -----

    @app.post("/api/login")
    def login(body: LoginRequest, response: Response):
        if not security.check_credentials(settings, body.login, body.password):
            return api_error(401, "Неверный логин или пароль")
        token, ttl = security.create_token(settings)
        # cookie нужен для <video>, <img> и скачивания PDF, где нельзя передать заголовок
        response.set_cookie(COOKIE_NAME, token, max_age=ttl, httponly=True, samesite="lax", path="/")
        return {"token": token, "expires_in": ttl}

    @app.post("/api/logout")
    def logout(response: Response):
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"status": "ok"}

    # ----- инспекции -----

    @app.post("/api/inspections", status_code=201, dependencies=[Depends(require_admin)])
    def create_inspection(
        file: UploadFile = File(...),
        title: str = Form(""),
        session: Session = Depends(get_session),
    ):
        filename = Path(file.filename or "video.mp4").name
        if not filename.lower().endswith(".mp4"):
            return api_error(415, "Принимаются только файлы MP4", E_VIDEO_INVALID)
        if (file.content_type or "").lower() not in ("video/mp4", "application/octet-stream", ""):
            return api_error(415, "Неверный тип файла: нужен video/mp4", E_VIDEO_INVALID)

        inspection_id = new_id()
        target = storage.video_path(settings.data_dir, inspection_id)
        storage.inspection_dir(settings.data_dir, inspection_id)
        try:
            storage.save_stream(file.file, target, settings.max_upload_bytes)
        except storage.FileTooLarge:
            storage.delete_inspection_dir(settings.data_dir, inspection_id)
            return api_error(413, f"Файл больше {settings.max_upload_mb} МБ")

        # сигнатура контейнера MP4: байты 4..8 — «ftyp»
        with open(target, "rb") as fh:
            head = fh.read(12)
        if head[4:8] != b"ftyp":
            storage.delete_inspection_dir(settings.data_dir, inspection_id)
            return api_error(422, "Файл не является корректным MP4", E_VIDEO_INVALID)
        try:
            meta = probe_video(str(target))
        except PipelineError as exc:
            storage.delete_inspection_dir(settings.data_dir, inspection_id)
            return api_error(422, exc.message, exc.code)

        title = title.strip() or Path(filename).stem
        insp = repo.create_inspection(session, inspection_id, title, filename, round(meta.duration_sec, 3))
        return {"id": insp.id, "title": insp.title, "status": insp.status}

    @app.get("/api/inspections", dependencies=[Depends(require_admin)])
    def list_inspections(session: Session = Depends(get_session)):
        return [inspection_summary(i, n) for i, n in repo.list_inspections(session)]

    def _get_or_404(session: Session, inspection_id: str):
        insp = repo.get_inspection(session, inspection_id)
        if insp is None:
            return None, api_error(404, "Инспекция не найдена")
        return insp, None

    @app.get("/api/inspections/{inspection_id}", dependencies=[Depends(require_admin)])
    def get_inspection(inspection_id: str, session: Session = Depends(get_session)):
        insp, err = _get_or_404(session, inspection_id)
        return err or inspection_detail(insp)

    @app.get("/api/inspections/{inspection_id}/findings", dependencies=[Depends(require_admin)])
    def get_findings(inspection_id: str, session: Session = Depends(get_session)):
        insp, err = _get_or_404(session, inspection_id)
        if err:
            return err
        return [finding_out(f) for f in repo.list_findings(session, inspection_id)]

    @app.get("/api/inspections/{inspection_id}/video", dependencies=[Depends(require_admin)])
    def get_video(inspection_id: str, session: Session = Depends(get_session)):
        insp, err = _get_or_404(session, inspection_id)
        if err:
            return err
        path = storage.video_path(settings.data_dir, inspection_id)
        if not path.is_file():
            return api_error(404, "Видео не найдено")
        # FileResponse поддерживает заголовок Range, поэтому плеер умеет перематывать
        return FileResponse(path, media_type="video/mp4", filename=None)

    @app.get("/api/inspections/{inspection_id}/frames/{name}", dependencies=[Depends(require_admin)])
    def get_frame(inspection_id: str, name: str):
        try:
            path = storage.frame_file(settings.data_dir, inspection_id, name)
        except storage.UnsafePath:
            return api_error(404, "Кадр не найден")
        if not path.is_file():
            return api_error(404, "Кадр не найден")
        return FileResponse(path, media_type=mimetypes.guess_type(name)[0] or "image/jpeg")

    @app.get("/api/inspections/{inspection_id}/report.pdf", dependencies=[Depends(require_admin)])
    def get_report(inspection_id: str, session: Session = Depends(get_session)):
        insp, err = _get_or_404(session, inspection_id)
        if err:
            return err
        if insp.status != STATUS_DONE:
            return api_error(409, "Отчёт доступен только для обработанных инспекций")
        from . import report

        path = report.ensure_report(session, settings, insp)
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"linesight-report-{inspection_id[:8]}.pdf",
        )

    # ----- находки -----

    @app.patch("/api/findings/{finding_id}", dependencies=[Depends(require_admin)])
    def patch_finding(finding_id: str, body: FindingPatch, session: Session = Depends(get_session)):
        finding = repo.set_finding_status(session, finding_id, body.status)
        if finding is None:
            return api_error(404, "Находка не найдена")
        return finding_out(finding)

    # ----- метрики -----

    @app.get("/api/metrics", dependencies=[Depends(require_admin)])
    def get_metrics(response: Response, session: Session = Depends(get_session)):
        response.headers["Cache-Control"] = "no-store"
        return repo.metrics(session)

    return app
