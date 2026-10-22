"""DB-backed cache for external metadata lookups keyed by IMDB id (``skyhook``, ``servarr``)."""

import json
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from ukr_torznab.db.upsert import upsert

HIT_TTL = timedelta(days=7)
MISS_TTL = timedelta(days=1)


async def read_cached(
    conn: AsyncConnection,
    table: sa.Table,
    imdb_id: int,
) -> tuple[bool, dict | None]:
    """Return ``(fresh, response)``; ``fresh`` is False when the entry is missing or expired."""
    row = (await conn.execute(select(table).where(table.c.imdbid == imdb_id))).first()
    if row is None:
        return False, None
    ttl = HIT_TTL if row.response else MISS_TTL
    if datetime.now(UTC) - row.updated_at.replace(tzinfo=UTC) >= ttl:
        return False, None
    return True, json.loads(row.response) if row.response else None


async def write_cached(
    conn: AsyncConnection,
    table: sa.Table,
    imdb_id: int,
    *,
    external_id_col: str,
    external_id: int | None,
    response: dict | None,
) -> None:
    values = {
        external_id_col: external_id,
        "response": json.dumps(response) if response else None,
        "updated_at": datetime.now(UTC),
    }
    await conn.execute(
        upsert(table, conn)
        .values({"imdbid": imdb_id, **values})
        .on_conflict_do_update(index_elements=["imdbid"], set_=values),
    )
