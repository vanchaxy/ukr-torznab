import asyncio
import hashlib
import logging
import os
import re
from pathlib import PurePosixPath

from sqlalchemy.ext.asyncio import AsyncEngine

from ukr_torznab.clients.qbittorrent import QBittorrentClient
from ukr_torznab.clients.utp import UtpClient, build_file_to_episode
from ukr_torznab.db.queries import get_releases_by_infohash
from ukr_torznab.models import Release, Tracker
from ukr_torznab.settings import (
    QBITTORRENT_CATEGORIES,
    QBITTORRENT_RENAME_ERROR_TAG,
    QBITTORRENT_RENAME_TAG,
)
from ukr_torznab.tasks.base import AbstractTask
from ukr_torznab.utils import VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)

_UTP_COMMENT_RE = re.compile(r"https://utp\.to/torrents/(\d+)")


def _sha256_of_sha1(sha1_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(sha1_hex)).hexdigest()


def _top_folder(files: list[dict]) -> str | None:
    if not any("/" in f.get("name", "") for f in files):
        return None
    return files[0]["name"].split("/")[0]


def _filter_videos(files: list[dict]) -> list[dict]:
    return [f for f in files if os.path.splitext(f.get("name", ""))[1].lower() in VIDEO_EXTENSIONS]


def _target_folder(release: Release) -> str:
    return release.tv_folder() if release.is_tv else release.movie_folder()


def _target_filename(release: Release, original_path: str, ext: str) -> str:
    if release.is_tv and release.file_to_episode:
        mapping = release.file_to_episode.get(original_path.lower())
        if mapping is not None:
            season, episode = mapping
            return release.episode_filename(season, episode, ext)
    return release.release_name() + ext


def _prepare_episode_map(release: Release, torrent_files: list[dict]) -> None:
    if release.is_tv and release.tracker is Tracker.utopia:
        release.file_to_episode = build_file_to_episode(release.season, torrent_files)
    if release.file_to_episode:
        release.file_to_episode = {k.lower(): v for k, v in release.file_to_episode.items()}


def _classify(torrents: list[dict]) -> tuple[list[tuple[str, str]], list[str]]:
    utp_jobs: list[tuple[str, str]] = []
    toloka_hashes: list[str] = []
    for torrent in torrents:
        qbt_hash = torrent["hash"]
        comment = torrent.get("comment") or ""
        utp_match = _UTP_COMMENT_RE.search(comment)
        if utp_match:
            utp_jobs.append((qbt_hash, utp_match.group(1)))
        elif "toloka" in comment:
            toloka_hashes.append(qbt_hash)
    return utp_jobs, toloka_hashes


class RenameTorrentsTask(AbstractTask):
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        qbt_client: QBittorrentClient,
        utp_client: UtpClient | None = None,
    ) -> None:
        self.engine = engine
        self.qbt_client = qbt_client
        self.utp_client = utp_client

    async def run_once(self) -> None:
        torrents = await self.qbt_client.get_stopped_torrents(
            categories=QBITTORRENT_CATEGORIES,
            exclude_tags={QBITTORRENT_RENAME_TAG, QBITTORRENT_RENAME_ERROR_TAG},
        )
        utp_jobs, toloka_hashes = _classify(torrents)

        await self._process_toloka(toloka_hashes)
        await self._process_utp(utp_jobs)

        await self.interruptible_sleep(60)

    async def _process_toloka(self, qbt_hashes: list[str]) -> None:
        if not qbt_hashes:
            return

        sha256_to_qbt = {_sha256_of_sha1(h): h for h in qbt_hashes}
        async with self.engine.connect() as conn:
            releases = await get_releases_by_infohash(conn, list(sha256_to_qbt.keys()))

        for release in releases:
            if not self.running:
                return
            qbt_hash = sha256_to_qbt.get(release.infohash_sha256)
            if qbt_hash is None:
                continue
            try:
                await self._rename_and_start(release, qbt_hash)
            except Exception:
                logger.exception("Failed to rename torrent %s hash=%s", release.id, qbt_hash)
                await self.qbt_client.add_tags(qbt_hash, [QBITTORRENT_RENAME_ERROR_TAG])

    async def _process_utp(self, jobs: list[tuple[str, str]]) -> None:
        for qbt_hash, utp_id in jobs:
            if not self.running:
                return
            if self.utp_client is None:
                logger.warning("UTP torrent id=%s skipped: no UTP client configured", utp_id)
                continue
            try:
                release = await self.utp_client.get_by_id(utp_id)
                if release is None:
                    logger.warning("UTP torrent id=%s not found via API, skipping", utp_id)
                    await self.qbt_client.add_tags(qbt_hash, [QBITTORRENT_RENAME_ERROR_TAG])
                    continue
                await self._rename_and_start(release, qbt_hash)
            except Exception:
                logger.exception("Failed to rename UTP torrent id=%s hash=%s", utp_id, qbt_hash)
                await self.qbt_client.add_tags(qbt_hash, [QBITTORRENT_RENAME_ERROR_TAG])

    async def _rename_and_start(self, release: Release, qbt_hash: str) -> None:
        torrent_files = await self.qbt_client.get_torrent_files(qbt_hash)
        _prepare_episode_map(release, torrent_files)

        await self.qbt_client.rename_torrent(qbt_hash, release.release_name())
        await self._apply_renames(release, qbt_hash, torrent_files)
        await self._finalize(qbt_hash)

        logger.info("Renamed & resumed torrent %s (hash=%s)", release.id, qbt_hash)

    async def _finalize(self, qbt_hash: str) -> None:
        await self.qbt_client.add_tags(qbt_hash, [QBITTORRENT_RENAME_TAG])
        await self.qbt_client.recheck(qbt_hash)
        await self.qbt_client.stop(qbt_hash)
        await self.qbt_client.start(qbt_hash)

    async def _apply_renames(
        self,
        release: Release,
        qbt_hash: str,
        all_files: list[dict],
    ) -> None:
        old_folder = _top_folder(all_files)
        video_files = _filter_videos(all_files)

        if not old_folder and len(all_files) == 1:
            await self._rename_bare_file(release, qbt_hash, all_files[0])
            return

        if len(video_files) == 1:
            await self._rename_solo_video(release, qbt_hash, video_files[0], old_folder)
            return

        if release.is_tv and release.file_to_episode:
            await self._rename_tv_pack(release, qbt_hash, video_files, old_folder)
            return

        if old_folder:
            await self._rename_folder(qbt_hash, old_folder, _target_folder(release))

    async def _rename_file(self, qbt_hash: str, old_path: str, new_path: str) -> None:
        await self.qbt_client.rename_file(qbt_hash, old_path, new_path)
        await self._wait_for_file_rename(qbt_hash, new_path)

    async def _rename_folder(self, qbt_hash: str, old_path: str, new_path: str) -> None:
        await self.qbt_client.rename_folder(qbt_hash, old_path, new_path)
        await self._wait_for_folder_rename(qbt_hash, old_path)

    async def _wait_for_file_rename(self, qbt_hash: str, new_path: str) -> None:
        for _ in range(60):
            files = await self.qbt_client.get_torrent_files(qbt_hash)
            if any(f.get("name") == new_path for f in files):
                return
            await asyncio.sleep(1)
        raise TimeoutError(f"rename did not complete in 60 s: expected {new_path!r}")

    async def _wait_for_folder_rename(self, qbt_hash: str, old_folder: str) -> None:
        prefix = old_folder + "/"
        for _ in range(60):
            files = await self.qbt_client.get_torrent_files(qbt_hash)
            if not any(f.get("name", "").startswith(prefix) for f in files):
                return
            await asyncio.sleep(1)
        raise TimeoutError(f"folder rename did not complete in 60 s: still has files under {old_folder!r}")

    async def _rename_bare_file(
        self,
        release: Release,
        qbt_hash: str,
        entry: dict,
    ) -> None:
        old = entry.get("name", "")
        new = _target_filename(release, old, os.path.splitext(old)[1])
        if old != new:
            await self._rename_file(qbt_hash, old, new)

    async def _rename_solo_video(
        self,
        release: Release,
        qbt_hash: str,
        entry: dict,
        old_folder: str | None,
    ) -> None:
        old_path = entry.get("name", "")
        old_basename = PurePosixPath(old_path).name
        ext = os.path.splitext(old_basename)[1]
        new_basename = _target_filename(release, old_path, ext)

        if not old_folder:
            await self._rename_file(qbt_hash, old_path, new_basename)
            return

        if old_basename != new_basename:
            await self._rename_file_in_folder(
                qbt_hash,
                old_folder,
                old_basename,
                new_basename,
            )
        await self._rename_folder_if_changed(qbt_hash, old_folder, _target_folder(release))

    async def _rename_tv_pack(
        self,
        release: Release,
        qbt_hash: str,
        video_files: list[dict],
        old_folder: str | None,
    ) -> None:
        mapping = release.file_to_episode or {}

        for entry in video_files:
            old_path = entry.get("name", "")
            episode = mapping.get(old_path.lower())
            if episode is None:
                continue
            season, ep_num = episode
            old_basename = PurePosixPath(old_path).name
            new_basename = release.episode_filename(
                season,
                ep_num,
                os.path.splitext(old_basename)[1],
            )
            if old_basename == new_basename:
                continue
            if old_folder:
                await self._rename_file_in_folder(
                    qbt_hash,
                    old_folder,
                    old_basename,
                    new_basename,
                )
            else:
                await self._rename_file(qbt_hash, old_path, new_basename)
            logger.debug("  file: %r → %r", old_basename, new_basename)

        if old_folder:
            await self._rename_folder_if_changed(qbt_hash, old_folder, release.tv_folder())

    async def _rename_file_in_folder(
        self,
        qbt_hash: str,
        folder: str,
        old_basename: str,
        new_basename: str,
    ) -> None:
        await self._rename_file(
            qbt_hash,
            f"{folder}/{old_basename}",
            f"{folder}/{new_basename}",
        )

    async def _rename_folder_if_changed(
        self,
        qbt_hash: str,
        old: str,
        new: str,
    ) -> None:
        if old != new:
            await self._rename_folder(qbt_hash, old, new)
