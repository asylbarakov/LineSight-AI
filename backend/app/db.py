from .config import get_settings

def ping_db():
    import psycopg

    cfg = get_settings()
    with psycopg.connect(
        host=cfg.db_host,
        port=cfg.db_port,
        dbname=cfg.db_name,
        user=cfg.db_user,
        password=cfg.db_password,
        connect_timeout=2,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() == (1,)
