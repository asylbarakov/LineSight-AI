"""Shared connection configuration at the API/worker infrastructure boundary."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class PostgresConnection:
    user: str
    password: str = field(repr=False)
    database: str
    host: str
    port: int


def postgres_settings(env: Mapping[str, str]) -> PostgresConnection:
    password = env.get("POSTGRES_PASSWORD", "")
    if not password:
        raise ValueError("POSTGRES_PASSWORD is required for PostgreSQL.")
    user = env.get("POSTGRES_USER", "linesight")
    database = env.get("POSTGRES_DB", "linesight")
    host = env.get("POSTGRES_HOST", "postgres")
    if not user.strip() or not database.strip() or not host.strip():
        raise ValueError("POSTGRES_USER, POSTGRES_DB and POSTGRES_HOST must not be blank.")
    try:
        port = int(env.get("POSTGRES_PORT", "5432"))
    except (TypeError, ValueError):
        raise ValueError("POSTGRES_PORT must be an integer between 1 and 65535.") from None
    if not 1 <= port <= 65535:
        raise ValueError("POSTGRES_PORT must be an integer between 1 and 65535.")
    return PostgresConnection(user, password, database, host, port)


def database_url_from_env(env: Mapping[str, str]) -> str:
    # Explicit URLs remain useful for host deployments and isolated SQLite tests.
    # Compose clears DATABASE_URL and supplies one shared set of POSTGRES_* fields.
    explicit = env.get("DATABASE_URL", "").strip()
    if explicit:
        return explicit
    if not any(key.startswith("POSTGRES_") for key in env):
        return "sqlite:///./linesight.db"
    connection = postgres_settings(env)
    # Lazy import keeps configuration-only tooling independent of installed ORM deps.
    from sqlalchemy.engine import URL
    return URL.create("postgresql+psycopg", username=connection.user,
                      password=connection.password, host=connection.host,
                      port=connection.port, database=connection.database).render_as_string(hide_password=False)
