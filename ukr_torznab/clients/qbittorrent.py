from typing import Any

import httpx
from httpx_limiter import Rate

from ukr_torznab.clients._http import make_client


class QBittorrentClient:
    def __init__(self, url: str, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._client = make_client(
            f"{url.rstrip('/')}/api/v2",
            rate=Rate.create(4, 1),
            timeout=30,
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        resp = await self._client.request(method, path, **kwargs)
        if resp.status_code == 403:
            # Not logged in yet, or the WebUI session expired.
            await self.login()
            resp = await self._client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp

    async def _get(self, path: str, **params: str) -> httpx.Response:
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, **data: str) -> None:
        await self._request("POST", path, data=data)

    async def login(self) -> None:
        resp = await self._client.post(
            "auth/login",
            data={"username": self._username, "password": self._password},
        )
        resp.raise_for_status()
        # qBittorrent 5 answers a login with 204 and no body, older versions "Ok.";
        # wrong credentials get 200 "Fails."
        if resp.text not in ("", "Ok."):
            raise RuntimeError("qBittorrent login failed: check the qBittorrent credentials")

    async def get_stopped_torrents(
        self,
        categories: set[str],
        exclude_tags: set[str],
    ) -> list[dict]:
        resp = await self._get("torrents/info", filter="stopped")
        return [
            torrent
            for torrent in resp.json()
            if torrent["category"] in categories
            and not {t.strip() for t in torrent["tags"].split(",")} & exclude_tags
        ]

    async def get_torrent_files(self, hash: str) -> list[dict]:
        resp = await self._get("torrents/files", hash=hash)
        return resp.json()

    async def rename_torrent(self, hash: str, name: str) -> None:
        await self._post("torrents/rename", hash=hash, name=name)

    async def rename_file(self, hash: str, old_path: str, new_path: str) -> None:
        await self._post("torrents/renameFile", hash=hash, oldPath=old_path, newPath=new_path)

    async def rename_folder(self, hash: str, old_path: str, new_path: str) -> None:
        await self._post("torrents/renameFolder", hash=hash, oldPath=old_path, newPath=new_path)

    async def add_tags(self, hash: str, tags: list[str]) -> None:
        await self._post("torrents/addTags", hashes=hash, tags=",".join(tags))

    async def start(self, hash: str) -> None:
        await self._post("torrents/start", hashes=hash)

    async def stop(self, hash: str) -> None:
        await self._post("torrents/stop", hashes=hash)

    async def recheck(self, hash: str) -> None:
        await self._post("torrents/recheck", hashes=hash)

    async def close(self) -> None:
        await self._client.aclose()
