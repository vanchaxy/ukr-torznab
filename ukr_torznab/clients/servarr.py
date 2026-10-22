from httpx_limiter import Rate
from sqlalchemy.ext.asyncio import AsyncConnection

from ukr_torznab.clients._cache import read_cached, write_cached
from ukr_torznab.clients._http import BROWSER_HEADERS, make_client
from ukr_torznab.db.tables import servarr as servarr_table


class ServarrClient:
    def __init__(self) -> None:
        self._client = make_client(
            "https://radarrapi.servarr.com/v1",
            rate=Rate.create(1, 1),
            follow_redirects=True,
            headers=BROWSER_HEADERS,
        )

    async def get_metadata(
        self,
        conn: AsyncConnection,
        imdb_id: int,
    ) -> dict | None:
        fresh, cached = await read_cached(conn, servarr_table, imdb_id)
        if fresh:
            return cached

        imdb_str = f"tt{imdb_id:07d}"
        tmdb_id: int | None = None
        response_data: dict | None = None

        r = await self._client.get(f"movie/imdb/{imdb_str}")
        if r.status_code == 200:
            for entry in r.json():
                if entry.get("ImdbId") == imdb_str:
                    tmdb_id = entry.get("TmdbId")
                    response_data = entry
                    break

        await write_cached(
            conn,
            servarr_table,
            imdb_id,
            external_id_col="tmdbid",
            external_id=tmdb_id,
            response=response_data,
        )
        return response_data

    async def close(self) -> None:
        await self._client.aclose()
