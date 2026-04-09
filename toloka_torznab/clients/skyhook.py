from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
from httpx_limiter import AsyncRateLimitedTransport, Rate
from httpx_limiter.aiolimiter import AiolimiterAsyncLimiter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from toloka_torznab.db.tables import skyhook as skyhook_table
from toloka_torznab.db.upsert import upsert


class SkyhookClient:
    """HTTP client for the Sonarr Skyhook API with built-in DB caching."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://skyhook.sonarr.tv/v1/tvdb",
            follow_redirects=True,
            headers={
                "accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8,"
                    "application/signed-exchange;v=b3;q=0.7"
                ),
                "accept-language": "en-US,en;q=0.9,uk;q=0.8,ru;q=0.7,cs;q=0.6",
                "cache-control": "max-age=0",
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/135.0.0.0 Safari/537.36"
                ),
            },
            transport=AsyncRateLimitedTransport.create(
                AiolimiterAsyncLimiter.create(Rate.create(1, 1)),
            ),
        )

    async def get_metadata(
        self,
        conn: AsyncConnection,
        imdb_id: int,
    ) -> dict | None:
        row = (
            await conn.execute(
                select(skyhook_table).where(skyhook_table.c.imdbid == imdb_id),
            )
        ).first()
        if row is not None:
            ttl = timedelta(days=7) if row.response else timedelta(days=1)
            if datetime.now(UTC) - row.updated_at.replace(tzinfo=UTC) < ttl:
                return json.loads(row.response) if row.response else None

        imdb_str = f"tt{imdb_id:07d}"
        tvdb_id: int | None = None
        response_data: dict | None = None

        r1 = await self._client.get(f"search/en/?term=imdb:{imdb_str}")
        if r1.status_code == 200:
            results = r1.json()
            for entry in results:
                if entry.get("imdbId") == imdb_str:
                    tvdb_id = entry.get("tvdbId")
                    break
            if tvdb_id is None and results:
                tvdb_id = results[0].get("tvdbId")

        if tvdb_id is not None:
            r2 = await self._client.get(f"shows/en/{tvdb_id}")
            if r2.status_code == 200:
                response_data = r2.json()

        values = {
            "tvdbid": tvdb_id,
            "response": json.dumps(response_data) if response_data else None,
            "updated_at": datetime.now(UTC),
        }
        await conn.execute(
            upsert(skyhook_table, conn)
            .values({"imdbid": imdb_id, **values})
            .on_conflict_do_update(index_elements=["imdbid"], set_=values),
        )

        return response_data

    async def aclose(self) -> None:
        await self._client.aclose()
