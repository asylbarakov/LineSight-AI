"""Общие фикстуры бэкенда: SQLite во временной папке, временные данные, синтетическое видео.

Импорты внутри фикстур: тесты без БД (хранилище, отчёт) не требуют SQLAlchemy.
"""

import pytest


@pytest.fixture(scope="session")
def blur_video(tmp_path_factory):
    from ml.make_synthetic import make_video

    path = tmp_path_factory.mktemp("synth") / "blur.mp4"
    make_video(path, duration=16.0, fps=10, blur=[(5.0, 11.0)], seed=5)
    return path


@pytest.fixture()
def settings(tmp_path):
    from app.config import Settings

    return Settings.from_env({
        "ADMIN_LOGIN": "admin", "ADMIN_PASSWORD": "pw", "SECRET_KEY": "k" * 40,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}", "DATA_DIR": str(tmp_path / "data"),
        "MAX_UPLOAD_MB": "5", "TASK_SOFT_TIME_LIMIT_SEC": "120",
    })


@pytest.fixture()
def session_factory(settings):
    from app.db import init_db, make_engine, make_session_factory

    engine = make_engine(settings.database_url)
    init_db(engine, retries=1)
    return make_session_factory(engine)
