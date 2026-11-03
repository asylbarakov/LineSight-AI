import logging
import os
import signal
import tempfile
from pathlib import Path
from threading import Event

LOG = logging.getLogger("linesight.worker")
STOP = Event()


def check_database() -> bool:
    import psycopg

    with psycopg.connect(
        host=os.getenv("DB_HOST", "postgres"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "linesight"),
        user=os.getenv("DB_USER", "linesight"),
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=2,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)


def check_storage() -> bool:
    root = Path(os.getenv("STORAGE_DIR", "/data"))
    if not root.is_dir():
        return False
    try:
        with tempfile.TemporaryFile(dir=root):
            pass
        return True
    except OSError:
        return False


def stop(signum: int, _frame: object) -> None:
    LOG.info("Received signal %s", signum)
    STOP.set()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    LOG.info("Worker started")

    while not STOP.is_set():
        try:
            db_ok = check_database()
        except Exception as exc:
            LOG.warning("Database unavailable: %s", type(exc).__name__)
            db_ok = False

        storage_ok = check_storage()
        if db_ok and storage_ok:
            LOG.info("Dependencies ready")
        else:
            LOG.warning("Dependency check: database=%s storage=%s", db_ok, storage_ok)
        STOP.wait(30)

    LOG.info("Worker stopped")


if __name__ == "__main__":
    main()
