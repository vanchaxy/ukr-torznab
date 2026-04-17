import logging
import re
from datetime import datetime
from typing import Any, cast
from zoneinfo import ZoneInfo

import httpx
import libtorrent as lt  # type: ignore[import-untyped]
from httpx_limiter import AsyncRateLimitedTransport, Rate
from httpx_limiter.aiolimiter import AiolimiterAsyncLimiter
from lxml import etree
from lxml.etree import _Element

from ukr_torznab.settings import TOLOKA_CATEGORIES

logger = logging.getLogger(__name__)

PAGE_SIZE = 90
KYIV_TZ = ZoneInfo("Europe/Kyiv")


def _xp(el: _Element, expr: str) -> list[Any]:
    return cast("list[Any]", el.xpath(expr))


class TolokaClient:
    def __init__(self, username, password):
        self._username = username
        self._password = password
        self._client = httpx.AsyncClient(
            base_url="https://toloka.to",
            follow_redirects=True,
            headers={
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "accept-language": "en-US,en;q=0.9,uk;q=0.8,ru;q=0.7,cs;q=0.6",
                "cache-control": "max-age=0",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            },
            transport=AsyncRateLimitedTransport.create(
                AiolimiterAsyncLimiter.create(Rate.create(1, 2)),
            ),
        )

    async def login(self):
        response = await self._client.post(
            "login.php",
            data={
                "username": self._username,
                "password": self._password,
                "autologin": "on",
                "ssl": "on",
                "redirect": "index.php?",
                "login": "Вхід",
            },
        )
        response.raise_for_status()

    async def get_recent_categories(self):
        params = [("f[]", x) for x in TOLOKA_CATEGORIES]
        cats = []
        for sort in (0, 8):
            response = await self._client.get("tracker.php", params=params + [("o", sort)])
            response.raise_for_status()
            dom = etree.HTML(response.text)
            cats.extend(
                [
                    h.split("=")[1]
                    for h in cast(
                        "list[str]",
                        dom.xpath("//td/a[contains(@href, 'tracker.php?f=')]/@href"),
                    )
                ],
            )

        return list(set(cats))

    async def get_category_page_topics(self, category_id, page_num, *, sort=0):
        response = await self._client.get(
            f"f{category_id}-{page_num * PAGE_SIZE}",
            params={"sort": sort},
        )
        response.raise_for_status()
        dom = etree.HTML(response.text)
        topics_table = cast(
            "list[_Element]",
            dom.xpath(
                '//table[@class="forumline"]/tr[td[span[@class="seedmed"]]]',
            ),
        )

        topics = []
        for topic_tr in topics_table:
            _, name_td, stats_td, size_td, added_on_td, updated_at_td = list(topic_tr)

            name_a = _xp(name_td, './/a[@class="topictitle"]')[0]
            name = name_a.text
            href = name_a.attrib["href"]
            if href.startswith("t"):
                id = int(href[1:])
            else:
                logger.warning("Unexpected topic href format: %r, skipping", href)
                continue

            status_d = _xp(name_td, './/span[@class="genred" or @class="gengold"]/b/text()')
            status = None
            if status_d:
                match status_d[0]:
                    case "Золото:":
                        status = "gold"
                    case "Срібло:":
                        status = "silver"
                    case "Бронза:":
                        status = "bronze"
                    case "Авторський реліз:":
                        status = "author"

            added_on_str = _xp(added_on_td, './/span[@class="gensmall"]')[0].text
            added_on = datetime.strptime(added_on_str, "%Y-%m-%d").astimezone()

            seeders = int(_xp(stats_td, './/span[@class="seedmed"]/b')[0].text)
            leechers = int(_xp(stats_td, './/span[@class="leechmed"]/b')[0].text)

            download_a = _xp(size_td, './/a[contains(@href,"download.php?id=")]')[0]
            download_id_str = download_a.attrib["href"].split("id=")[1]
            if download_id_str:
                download_id = int(download_id_str)
            else:
                continue
            size = re.findall(r"\d+(?:\.\d+)?", download_a.text)[0]

            updated_at_str = _xp(updated_at_td, './/span[@class="postdetails"]')[0].text
            updated_at = (
                datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M")
                .replace(tzinfo=KYIV_TZ)
                .astimezone()
            )

            topics.append(
                {
                    "id": id,
                    "name": name,
                    "status": status,
                    "seeders": seeders,
                    "leechers": leechers,
                    "size": size,
                    "download_id": download_id,
                    "added_on": added_on,
                    "updated_at": updated_at,
                },
            )

        return topics

    async def download_topic(self, id):
        response = await self._client.get(f"t{id}")
        response.raise_for_status()

        try:
            dom = etree.HTML(response.text)
            dom_list = cast(
                "list[_Element]",
                dom.xpath(
                    '//table[@class="forumline"]/tr[.//div[@class="files-wrap"]]',
                ),
            )
            if len(dom_list) != 1:
                return None
        except Exception:
            return None
        return response.text

    async def download_torrent(self, id):
        response = await self._client.get("download.php", params={"id": id})
        response.raise_for_status()
        try:
            lt.bdecode(response.content)
        except Exception:
            return None
        return response.content

    async def close(self):
        await self._client.aclose()
