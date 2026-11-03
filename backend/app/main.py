import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .db import ping_db
from .storage import storage_writable

logger = logging.getLogger(__name__)
app = FastAPI(title="LineSight AI API")

@app.get("/health", tags=["system"])
def health() -> JSONResponse:
    try:
        db_ok = ping_db()
    except Exception as exc:
        logger.warning("DB health check failed: %s", type(exc).__name__)
        db_ok = False

    storage_ok = storage_writable()
    healthy = db_ok and storage_ok
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ok" if healthy else "degraded",
            "service": "api",
            "database": "ok" if db_ok else "unavailable",
            "storage": "ok" if storage_ok else "unavailable",
        },
    )
