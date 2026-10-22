from httpx_limiter import Rate
from sqlalchemy.ext.asyncio import AsyncConnection

from ukr_torznab.clients._cache import read_cached, write_cached
from ukr_torznab.clients._http import BROWSER_HEADERS, make_client
from ukr_torznab.db.tables import skyhook as skyhook_table


class SkyhookClient:
    def __init__(self) -> None:
        self._client = make_client(
            "https://skyhook.sonarr.tv/v1/tvdb",
            rate=Rate.create(1, 1),
            follow_redirects=True,
            headers=BROWSER_HEADERS,
        )

    async def get_metadata(
        self,
        conn: AsyncConnection,
        imdb_id: int,
    ) -> dict | None:
        fresh, cached = await read_cached(conn, skyhook_table, imdb_id)
        if fresh:
            return cached

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

        await write_cached(
            conn,
            skyhook_table,
            imdb_id,
            external_id_col="tvdbid",
            external_id=tvdb_id,
            response=response_data,
        )
        return response_data

    async def close(self) -> None:
        await self._client.aclose()
