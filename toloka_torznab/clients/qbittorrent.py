import logging

import httpx

logger = logging.getLogger(__name__)


class QBittorrentClient:
    def __init__(self, url: str, username: str, password: str) -> None:
        self._url = url.rstrip("/")
        self._username = username
        self._password = password
        self._client = httpx.AsyncClient(timeout=30)

    async def login(self) -> None:
        resp = await self._client.post(
            f"{self._url}/api/v2/auth/login",
            data={"username": self._username, "password": self._password},
        )
        resp.raise_for_status()
        if resp.text == "Fails.":
            raise RuntimeError("qBittorrent login failed: bad credentials")
        logger.info("qBittorrent login OK")

    async def get_paused_torrents(self) -> list[dict]:
        resp = await self._client.get(
            f"{self._url}/api/v2/torrents/info",
            params={"filter": "paused"},
        )
        resp.raise_for_status()
        return resp.json()

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

    async def resume(self, hash: str) -> None:
        resp = await self._client.post(
            f"{self._url}/api/v2/torrents/resume",
            data={"hashes": hash},
        )
        resp.raise_for_status()

    async def close(self) -> None:
        await self._client.aclose()
