"""Вход одного администратора и JWT (задача 30). Ролей нет."""

from __future__ import annotations

import hmac
import time

import jwt

from .config import Settings

ALGORITHM = "HS256"


def check_credentials(settings: Settings, login: str, password: str) -> bool:
    """Сравнение за постоянное время. Оба поля сравниваются всегда, без раннего выхода."""
    ok_login = hmac.compare_digest(login.encode("utf-8"), settings.admin_login.encode("utf-8"))
    ok_pass = hmac.compare_digest(password.encode("utf-8"), settings.admin_password.encode("utf-8"))
    return ok_login and ok_pass


def create_token(settings: Settings, now: float | None = None) -> tuple[str, int]:
    """Возвращает (токен, срок жизни в секундах)."""
    now = time.time() if now is None else now
    ttl = int(settings.token_ttl_hours * 3600)
    payload = {"sub": settings.admin_login, "iat": int(now), "exp": int(now) + ttl}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM), ttl


def verify_token(settings: Settings, token: str) -> bool:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return False
    return payload.get("sub") == settings.admin_login
