from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session

from .config import get_settings


@lru_cache
def get_engine() -> Engine:
    cfg = get_settings()

    url = URL.create(
        drivername="postgresql+psycopg",
        username=cfg.db_user,
        password=cfg.db_password,
        host=cfg.db_host,
        port=cfg.db_port,
        database=cfg.db_name,
    )

    return create_engine(
        url,
        pool_pre_ping=True,
    )


def new_session() -> Session:
    return Session(get_engine())
