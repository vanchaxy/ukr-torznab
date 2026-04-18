import logging

import httpx
from httpx_limiter import AsyncRateLimitedTransport, Rate
from httpx_limiter.aiolimiter import AiolimiterAsyncLimiter

logger = logging.getLogger(__name__)


class QBittorrentClient:
    def __init__(self, url: str, username: str, password: str) -> None:
        self._url = url.rstrip("/")
        self._username = username
        self._password = password
        self._client = httpx.AsyncClient(
            timeout=30,
            transport=AsyncRateLimitedTransport.create(
                AiolimiterAsyncLimiter.create(Rate.create(1, 1)),
            ),
        )

    async def login(self) -> None:
        resp = await self._client.post(
            f"{self._url}/api/v2/auth/login",
            data={"username": self._username, "password": self._password},
        )
        resp.raise_for_status()
        if resp.text == "Fails.":
            raise RuntimeError("qBittorrent login failed: bad credentials")
        logger.info("qBittorrent login OK")

    async def get_stopped_torrents(self, categories) -> list[dict]:
        resp = await self._client.get(
            f"{self._url}/api/v2/torrents/info",
            params={"filter": "stopped"},
        )
        resp.raise_for_status()
        torrents = []
        for torrent in resp.json():
            if torrent["category"] not in categories:
                continue
            tags = [t.strip() for t in torrent["tags"].split(",") if t.strip()]
            if "renamed" in tags:
                continue
            torrents.append(torrent)
        return torrents

    async def get_torrent_files(self, hash: str) -> list[dict]:
        resp = await self._client.get(
            f"{self._url}/api/v2/torrents/files",
            params={"hash": hash},
        )
        resp.raise_for_status()
        return resp.json()

    async def rename_torrent(self, hash: str, name: str) -> None:
        resp = await self._client.post(
            f"{self._url}/api/v2/torrents/rename",
            data={"hash": hash, "name": name},
        )
        resp.raise_for_status()

    async def rename_file(self, hash: str, old_path: str, new_path: str) -> None:
        resp = await self._client.post(
            f"{self._url}/api/v2/torrents/renameFile",
            data={"hash": hash, "oldPath": old_path, "newPath": new_path},
        )
        resp.raise_for_status()

    async def add_tags(self, hash: str, tags: list[str]) -> None:
        resp = await self._client.post(
            f"{self._url}/api/v2/torrents/addTags",
            data={"hashes": hash, "tags": ",".join(tags)},
        )
        resp.raise_for_status()

    async def rename_folder(self, hash: str, old_path: str, new_path: str) -> None:
        resp = await self._client.post(
            f"{self._url}/api/v2/torrents/renameFolder",
            data={"hash": hash, "oldPath": old_path, "newPath": new_path},
        )
        resp.raise_for_status()

    async def start(self, hash: str) -> None:
        resp = await self._client.post(
            f"{self._url}/api/v2/torrents/start",
            data={"hashes": hash},
        )
        resp.raise_for_status()

    async def close(self) -> None:
        await self._client.aclose()
