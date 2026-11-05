import asyncio
import logging
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx
from httpx_limiter import Rate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from ukr_torznab.clients._http import BROWSER_HEADERS, make_client
from ukr_torznab.clients.zeroday.parser import (
    BASE_URL,
    ListRow,
    build_release,
    parse_list,
    parse_topic,
)
from ukr_torznab.db.tables import zeroday_topic
from ukr_torznab.db.upsert import upsert
from ukr_torznab.models import Release

logger = logging.getLogger(__name__)

# 0day is a windows-1251 site, query strings included.
ENCODING = "cp1251"

# Topic pages fetched per search at most, so one search stays well inside indexer timeouts at
# the 1 request / 2 s rate. Topics left over are fetched by the next search that lists them.
FETCH_BUDGET = 20


class ZerodayClient:
    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._client = make_client(
            BASE_URL,
            rate=Rate.create(1, 2),
            follow_redirects=True,
            headers=BROWSER_HEADERS,
            timeout=30,
        )
        self._login_lock = asyncio.Lock()

    async def login(self) -> None:
        response = await self._client.post(
            "takelogin.php",
            content=urlencode(
                {
                    "username": self._username,
                    "password": self._password,
                    "returnto": "/browse.php",
                },
                encoding=ENCODING,
            ),
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        if not self._logged_in(response):
            raise RuntimeError("0day login failed: check ZERODAY_USERNAME and ZERODAY_PASSWORD")

    @staticmethod
    def _logged_in(response: httpx.Response) -> bool:
        return b"logout.php" in response.content

    async def _get(self, url: str) -> httpx.Response:
        response = await self._client.get(url)
        if (
            response.is_success
            and response.headers.get("content-type", "").startswith("text/html")
            and not self._logged_in(response)
        ):
            # Concurrent callers may each log in again; rare and harmless.
            async with self._login_lock:
                logger.info("0day session expired, logging in again")
                await self.login()
            response = await self._client.get(url)
        response.raise_for_status()
        return response

    async def browse(self, query: str | None, categories: set[int]) -> list[ListRow]:
        params: list[tuple[str, str | int]] = [(f"c{c}", 1) for c in sorted(categories)]
        if query:
            params.append(("search", query))
        response = await self._get("browse.php?" + urlencode(params, encoding=ENCODING))
        return [
            r for r in parse_list(response.content.decode(ENCODING)) if r.category in categories
        ]

    async def download_torrent(self, id: int) -> bytes | None:
        # Without a name 0day answers with an HTML page; any name works.
        response = await self._get(f"download.php?id={id}&name={id}.torrent")
        if not response.content.startswith(b"d") or not response.content.endswith(b"e"):
            return None
        return response.content

    async def releases(self, engine: AsyncEngine, rows: list[ListRow]) -> list[Release]:
        """Releases for the listed topics, parsed from cached topic pages where still current."""
        async with engine.connect() as conn:
            cached = {
                r.id: r
                for r in await conn.execute(
                    select(zeroday_topic).where(zeroday_topic.c.id.in_([r.id for r in rows])),
                )
            }

        budget = FETCH_BUDGET
        releases = []
        for row in rows:
            hit = cached.get(row.id)
            if hit is not None and hit.title == row.title and hit.size == row.size:
                html = hit.html
                fresh = False
            elif budget > 0:
                budget -= 1
                try:
                    fresh = True
                    html = (await self._get(f"details.php?id={row.id}")).content.decode(ENCODING)
                except httpx.HTTPError:
                    logger.warning("0day topic %s: fetch failed", row.id, exc_info=True)
                    continue
                values = {
                    "title": row.title,
                    "size": row.size,
                    "html": html,
                    "fetched_at": datetime.now(UTC),
                }
                async with engine.begin() as conn:
                    await conn.execute(
                        upsert(zeroday_topic, conn)
                        .values(id=row.id, **values)
                        .on_conflict_do_update(index_elements=["id"], set_=values),
                    )
            else:
                continue

            topic = parse_topic(html)
            if topic is None:
                logger.warning("0day topic %s: no description", row.id)
                continue
            release = build_release(row, topic)
            if fresh and not release.audio_lang:
                logger.info("0day topic %s: no audio language found", row.id)
            releases.append(release)
        return releases

    async def close(self) -> None:
        await self._client.aclose()
