from alembic import context

from app.database import get_engine
from app.models import Base


target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = get_engine()

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not configured")
else:
    run_migrations_online()
