import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    storage_dir: Path

def get_settings() -> Settings:
    return Settings(
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_name=os.getenv("DB_NAME", "linesight"),
        db_user=os.getenv("DB_USER", "linesight"),
        db_password=os.getenv("DB_PASSWORD", ""),
        storage_dir=Path(os.getenv("STORAGE_DIR", "/data")),
    )
