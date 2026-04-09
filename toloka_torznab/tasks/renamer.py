import asyncio
import hashlib
import json
import logging
import os
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from toloka_torznab.clients.qbittorrent import QBittorrentClient
from toloka_torznab.db.tables import release
from toloka_torznab.naming import episode_filename, movie_filename, movie_folder, tv_folder
from toloka_torznab.tasks.base import AbstractTask

logger = logging.getLogger(__name__)

_VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".mov"}


def _sha256_of_sha1(sha1_hex: str) -> str:
    raw = bytes.fromhex(sha1_hex)
    return hashlib.sha256(raw).hexdigest()


class RenameTorrentsTask(AbstractTask):
    def __init__(self, *, engine: AsyncEngine, qbt_client: QBittorrentClient) -> None:
        self.engine = engine
        self.qbt_client = qbt_client

    async def run_once(self) -> None:
        paused = await self.qbt_client.get_paused_torrents()
        if not paused:
            await asyncio.sleep(60)
            return

        sha256_to_qbt: dict[str, str] = {}
        for t in paused:
            qbt_hash = t.get("hash", "")
            if qbt_hash:
                sha256_to_qbt[_sha256_of_sha1(qbt_hash)] = qbt_hash

        if not sha256_to_qbt:
            await asyncio.sleep(60)
            return

        async with self.engine.connect() as conn:
            rows = (
                await conn.execute(
                    select(
                        release.c.id,
                        release.c.title,
                        release.c.year,
                        release.c.content_type,
                        release.c.season,
                        release.c.season_complete,
                        release.c.file_to_episode,
                        release.c.quality,
                        release.c.resolution,
                        release.c.codec,
                        release.c.audio_types,
                        release.c.audio_sources,
                        release.c.audio_lang,
                        release.c.subtitle_lang,
                        release.c.release_group,
                        release.c.author,
                        release.c.infohash_sha256,
                    ).where(
                        release.c.infohash_sha256.in_(list(sha256_to_qbt.keys())),
                        release.c.result == "ok",
                    ),
                )
            ).fetchall()

        for row in rows:
            qbt_hash = sha256_to_qbt.get(row.infohash_sha256)
            if not qbt_hash:
                continue
            try:
                await self._rename_and_resume(row, qbt_hash)
            except Exception:
                logger.exception("Failed to rename torrent %s (hash=%s)", row.id, qbt_hash)

        await asyncio.sleep(60)

    async def _rename_and_resume(self, row, qbt_hash: str) -> None:
        is_tv = row.content_type == "tv"

        file_to_episode: dict[str, list[int]] | None = None
        if row.file_to_episode:
            file_to_episode = {k: v for k, v in json.loads(row.file_to_episode).items()}

        if is_tv and file_to_episode and not row.season_complete:
            await self._rename_tv_episodes(row, qbt_hash, file_to_episode)
        elif is_tv and row.season_complete:
            seasons_in_row = {row.season} if row.season is not None else None
            folder = tv_folder(row, seasons=seasons_in_row)
            await self.qbt_client.rename_torrent(qbt_hash, folder)
            await self.qbt_client.resume(qbt_hash)
            logger.info("Renamed & resumed season pack %s → %r", row.id, folder)
        else:
            await self._rename_movie(row, qbt_hash)

    async def _rename_tv_episodes(
        self,
        row,
        qbt_hash: str,
        file_to_episode: dict[str, list[int]],
    ) -> None:
        seasons: set[int] = {se for se, _ep in file_to_episode.values()}
        folder = tv_folder(row, seasons=seasons)

        torrent_files = await self.qbt_client.get_torrent_files(qbt_hash)
        for f in torrent_files:
            old_path: str = f.get("name", "")
            filename = PurePosixPath(old_path).name
            if filename not in file_to_episode:
                continue
            s, e = file_to_episode[filename][0], file_to_episode[filename][1]
            ext = os.path.splitext(filename)[1]
            new_path = episode_filename(row, s, e, ext)
            if old_path != new_path:
                await self.qbt_client.rename_file(qbt_hash, old_path, new_path)
                logger.debug("  file: %r → %r", old_path, new_path)

        await self.qbt_client.rename_torrent(qbt_hash, folder)
        await self.qbt_client.resume(qbt_hash)
        logger.info("Renamed & resumed TV torrent %s → %r", row.id, folder)

    async def _rename_movie(self, row, qbt_hash: str) -> None:
        torrent_files = await self.qbt_client.get_torrent_files(qbt_hash)
        video_files = [
            f
            for f in torrent_files
            if os.path.splitext(f.get("name", ""))[1].lower() in _VIDEO_EXTS
        ]
        if not video_files:
            logger.warning("No video file found for movie torrent %s, skipping", row.id)
            return

        old_path: str = video_files[0]["name"]
        ext = os.path.splitext(PurePosixPath(old_path).name)[1]
        new_name = movie_filename(row, ext)

        if old_path != new_name:
            await self.qbt_client.rename_file(qbt_hash, old_path, new_name)

        if "/" in old_path:
            await self.qbt_client.rename_torrent(qbt_hash, movie_folder(row))

        await self.qbt_client.resume(qbt_hash)
        logger.info("Renamed & resumed movie %s: %r → %r", row.id, old_path, new_name)
