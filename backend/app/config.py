"""Настройки бэкенда из переменных окружения (.env)."""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass

from .database_config import database_url_from_env

log = logging.getLogger("linesight.config")

DEFAULT_PASSWORD = "change-me"


@dataclass(frozen=True)
class Settings:
    admin_login: str
    admin_password: str
    secret_key: str
    token_ttl_hours: float
    database_url: str
    data_dir: str
    max_upload_mb: int
    poll_interval_sec: float
    task_soft_time_limit_sec: int

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @classmethod
    def from_env(cls, env: dict | None = None) -> "Settings":
        e = os.environ if env is None else env
        secret = e.get("SECRET_KEY") or ""
        if not secret or secret.startswith("change-me"):
            # без явного секрета токены живут до перезапуска API
            secret = secrets.token_urlsafe(48)
            log.warning("SECRET_KEY не задан: сгенерирован временный ключ, токены сбросятся при перезапуске")
        password = e.get("ADMIN_PASSWORD", DEFAULT_PASSWORD)
        if password == DEFAULT_PASSWORD:
            log.warning("ADMIN_PASSWORD оставлен по умолчанию — поменяйте его в .env")
        return cls(
            admin_login=e.get("ADMIN_LOGIN", "admin"),
            admin_password=password,
            secret_key=secret,
            token_ttl_hours=float(e.get("TOKEN_TTL_HOURS", 12)),
            database_url=database_url_from_env(e),
            data_dir=e.get("DATA_DIR", "./data"),
            max_upload_mb=int(e.get("MAX_UPLOAD_MB", 500)),
            poll_interval_sec=float(e.get("POLL_INTERVAL_SEC", 1.0)),
            task_soft_time_limit_sec=int(e.get("TASK_SOFT_TIME_LIMIT_SEC", 900)),
        )
