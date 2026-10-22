from alembic import context
from sqlalchemy import create_engine, pool

cfg = context.config


def run_migrations() -> None:
    url_str = cfg.get_main_option("sqlalchemy.url")

    engine = create_engine(url_str, poolclass=pool.NullPool)

    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=None)

        with context.begin_transaction():
            context.run_migrations()


run_migrations()
