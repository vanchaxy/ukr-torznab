from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncConnection


def upsert(table, conn: AsyncConnection):
    """Return a dialect-specific Insert that supports on_conflict_do_update."""
    if conn.engine.dialect.name == "postgresql":
        return pg_insert(table)
    return sqlite_insert(table)
