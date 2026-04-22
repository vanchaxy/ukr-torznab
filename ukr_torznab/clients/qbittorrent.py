import httpx
from httpx_limiter import AsyncRateLimitedTransport, Rate
from httpx_limiter.aiolimiter import AiolimiterAsyncLimiter


class QBittorrentClient:
    def __init__(self, url: str, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._client = httpx.AsyncClient(
            base_url=f"{url.rstrip('/')}/api/v2",
            timeout=30,
            transport=AsyncRateLimitedTransport.create(
                AiolimiterAsyncLimiter.create(Rate.create(1, 1)),
            ),
        )

    async def login(self) -> None:
        resp = await self._client.post(
            "auth/login",
            data={"username": self._username, "password": self._password},
        )
        resp.raise_for_status()

    async def get_stopped_torrents(
        self,
        categories: set[str],
        exclude_tags: set[str],
    ) -> list[dict]:
        resp = await self._client.get(
            "torrents/info",
            params={"filter": "stopped"},
        )
        resp.raise_for_status()

        return [
            torrent
            for torrent in resp.json()
            if torrent["category"] in categories
            and not {t.strip() for t in torrent["tags"].split(",")} & exclude_tags
        ]

    async def get_torrent_files(self, hash: str) -> list[dict]:
        resp = await self._client.get(
            "torrents/files",
            params={"hash": hash},
        )
        resp.raise_for_status()
        return resp.json()

    async def rename_torrent(self, hash: str, name: str) -> None:
        resp = await self._client.post(
            "torrents/rename",
            data={"hash": hash, "name": name},
        )
        resp.raise_for_status()

    async def rename_file(self, hash: str, old_path: str, new_path: str) -> None:
        resp = await self._client.post(
            "/torrents/renameFile",
            data={"hash": hash, "oldPath": old_path, "newPath": new_path},
        )
        resp.raise_for_status()

    async def add_tags(self, hash: str, tags: list[str]) -> None:
        resp = await self._client.post(
            "torrents/addTags",
            data={"hashes": hash, "tags": ",".join(tags)},
        )
        resp.raise_for_status()

    async def rename_folder(self, hash: str, old_path: str, new_path: str) -> None:
        resp = await self._client.post(
            "torrents/renameFolder",
            data={"hash": hash, "oldPath": old_path, "newPath": new_path},
        )
        resp.raise_for_status()

    async def start(self, hash: str) -> None:
        resp = await self._client.post(
            "torrents/start",
            data={"hashes": hash},
        )
        resp.raise_for_status()

    async def stop(self, hash: str) -> None:
        resp = await self._client.post(
            "torrents/stop",
            data={"hashes": hash},
        )
        resp.raise_for_status()

    async def recheck(self, hash: str) -> None:
        resp = await self._client.post(
            "torrents/recheck",
            data={"hashes": hash},
        )
        resp.raise_for_status()

    async def close(self) -> None:
        await self._client.aclose()
