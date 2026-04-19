import asyncio
import hashlib
import json
import logging
import os
import re
from pathlib import PurePosixPath

from sqlalchemy.ext.asyncio import AsyncEngine

from ukr_torznab.clients.qbittorrent import QBittorrentClient
from ukr_torznab.clients.utp import UtpClient, extract_episode_numbers
from ukr_torznab.db.queries import get_releases_by_infohash
from ukr_torznab.naming import episode_filename, release_name, tv_folder
from ukr_torznab.tasks.base import AbstractTask
from ukr_torznab.tasks.scraper.parse_topics.utils import VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)

_UTP_COMMENT_RE = re.compile(r"https://utp\.to/torrents/(\d+)")


def _sha256_of_sha1(sha1_hex: str) -> str:
    raw = bytes.fromhex(sha1_hex)
    return hashlib.sha256(raw).hexdigest()


def _build_file_to_episode(row: dict, torrent_files: list[dict]) -> dict[str, list[int]] | None:
    video_files = [
        f
        for f in torrent_files
        if os.path.splitext(f.get("name", ""))[1].lower() in VIDEO_EXTENSIONS
    ]
    if not video_files:
        return None
    paths = [f["name"] for f in video_files]
    ep_map = extract_episode_numbers(paths)
    if ep_map is None:
        return None
    season = row.get("season") or 1
    return {filename.lower(): [season, ep] for filename, ep in ep_map.items()}


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
        stopped = await self.qbt_client.get_stopped_torrents(categories=["movies", "tv"])
        for _ in range(60):
            if not self.running:
                return
            await asyncio.sleep(1)

        utp_torrents: list[tuple[str, str]] = []  # (qbt_hash, utp_id)
        toloka_hashes: list[str] = []

        for torrent in stopped:
            qbt_hash = torrent["hash"]
            comment = torrent.get("comment") or ""
            utp_id = _UTP_COMMENT_RE.search(comment)
            if utp_id:
                utp_torrents.append((qbt_hash, utp_id.group(1)))
            elif "toloka" in comment:
                toloka_hashes.append(qbt_hash)

        for qbt_hash, utp_id in utp_torrents:
            if not self.running:
                return
            if self.utp_client is None:
                logger.warning("UTP torrent id=%s skipped: no UTP client configured", utp_id)
                continue
            try:
                row = await self.utp_client.get_by_id(utp_id)
                if row is None:
                    logger.warning("UTP torrent id=%s not found via API, skipping", utp_id)
                    await self.qbt_client.add_tags(qbt_hash, ["rename-error"])
                    continue
                await self._rename_and_start(row, qbt_hash)
            except Exception:
                logger.exception("Failed to rename UTP torrent id=%s hash=%s", utp_id, qbt_hash)
                await self.qbt_client.add_tags(qbt_hash, ["rename-error"])

        if toloka_hashes:
            sha256_to_qbt = {_sha256_of_sha1(h): h for h in toloka_hashes}
            async with self.engine.connect() as conn:
                rows = await get_releases_by_infohash(conn, list(sha256_to_qbt.keys()))
            for row in rows:
                if not self.running:
                    return
                qbt_hash = sha256_to_qbt.get(row["infohash_sha256"])
                if not qbt_hash:
                    continue
                try:
                    await self._rename_and_start(row, qbt_hash)
                except Exception:
                    logger.exception("Failed to rename torrent %s hash=%s", row["id"], qbt_hash)
                    await self.qbt_client.add_tags(qbt_hash, ["rename-error"])

        for _ in range(60):
            if not self.running:
                return
            await asyncio.sleep(1)

    async def _rename_and_start(self, row: dict, qbt_hash: str) -> None:
        is_tv = row.get("content_type") == "tv"
        torrent_files = await self.qbt_client.get_torrent_files(qbt_hash)

        file_to_episode: dict[str, list[int]] | None = None
        if is_tv:
            if "file_to_episode" in row:
                raw_fte = row["file_to_episode"]
                if raw_fte:
                    file_to_episode = {k.lower(): v for k, v in json.loads(raw_fte).items()}
            else:
                file_to_episode = _build_file_to_episode(row, torrent_files)

        await self.qbt_client.rename_torrent(qbt_hash, release_name(row))
        await self._apply_renames(row, qbt_hash, torrent_files, is_tv, file_to_episode)
        await self.qbt_client.add_tags(qbt_hash, ["renamed"])
        await self.qbt_client.start(qbt_hash)
        logger.info("Renamed & resumed torrent %s (hash=%s)", row.get("id"), qbt_hash)

    async def _apply_renames(
        self,
        row: dict,
        qbt_hash: str,
        all_files: list[dict],
        is_tv: bool,
        file_to_episode: dict[str, list[int]] | None,
    ) -> None:
        has_folder = any("/" in f.get("name", "") for f in all_files)
        old_folder = all_files[0]["name"].split("/")[0] if has_folder else None
        video_files = [
            f
            for f in all_files
            if os.path.splitext(f.get("name", ""))[1].lower() in VIDEO_EXTENSIONS
        ]

        if not has_folder and len(all_files) == 1:
            await self._rename_single_file(row, qbt_hash, all_files[0], is_tv, file_to_episode)
        elif len(video_files) == 1:
            await self._rename_single_video(
                row,
                qbt_hash,
                video_files[0],
                is_tv,
                file_to_episode,
                old_folder,
            )
        elif not is_tv:
            if old_folder:
                await self.qbt_client.rename_folder(qbt_hash, old_folder, release_name(row))
        elif file_to_episode:
            await self._rename_tv_episodes(row, qbt_hash, video_files, file_to_episode, old_folder)
        elif old_folder:
            season = row.get("season")
            await self.qbt_client.rename_folder(
                qbt_hash,
                old_folder,
                tv_folder(row, seasons=[season] if season else None),
            )

    async def _rename_single_file(
        self,
        row: dict,
        qbt_hash: str,
        file_entry: dict,
        is_tv: bool,
        file_to_episode: dict[str, list[int]] | None,
    ) -> None:
        old = file_entry.get("name", "")
        ext = os.path.splitext(old)[1]
        if is_tv and file_to_episode and old.lower() in file_to_episode:
            s, e = file_to_episode[old.lower()]
            new_name = episode_filename(row, s, e, ext)
        else:
            new_name = release_name(row) + ext
        if old != new_name:
            await self.qbt_client.rename_file(qbt_hash, old, new_name)

    async def _rename_single_video(
        self,
        row: dict,
        qbt_hash: str,
        video_entry: dict,
        is_tv: bool,
        file_to_episode: dict[str, list[int]] | None,
        old_folder: str | None,
    ) -> None:
        old_path = video_entry.get("name", "")
        old_basename = PurePosixPath(old_path).name
        ext = os.path.splitext(old_basename)[1]

        if is_tv and file_to_episode and old_path.lower() in file_to_episode:
            s, e = file_to_episode[old_path.lower()]
            new_folder = tv_folder(row, seasons=[s])
            new_basename = episode_filename(row, s, e, ext)
        else:
            new_folder = release_name(row)
            new_basename = release_name(row) + ext

        if old_folder:
            if old_basename != new_basename:
                await self.qbt_client.rename_file(
                    qbt_hash,
                    f"{old_folder}/{old_basename}",
                    f"{old_folder}/{new_basename}",
                )
            if old_folder != new_folder:
                await self.qbt_client.rename_folder(qbt_hash, old_folder, new_folder)
        else:
            await self.qbt_client.rename_file(qbt_hash, old_path, new_basename)

    async def _rename_tv_episodes(
        self,
        row: dict,
        qbt_hash: str,
        video_files: list[dict],
        file_to_episode: dict[str, list[int]],
        old_folder: str | None,
    ) -> None:
        seasons = list({v[0] for v in file_to_episode.values()})
        new_folder = tv_folder(row, seasons=seasons or None)

        for f in video_files:
            old_path = f.get("name", "")
            old_basename = PurePosixPath(old_path).name
            if old_path.lower() not in file_to_episode:
                continue
            s, e = file_to_episode[old_path.lower()]
            new_basename = episode_filename(row, s, e, os.path.splitext(old_basename)[1])
            if old_basename == new_basename:
                continue
            if old_folder:
                await self.qbt_client.rename_file(
                    qbt_hash,
                    f"{old_folder}/{old_basename}",
                    f"{old_folder}/{new_basename}",
                )
            else:
                await self.qbt_client.rename_file(qbt_hash, old_path, new_basename)
            logger.debug("  file: %r → %r", old_basename, new_basename)

        if old_folder and old_folder != new_folder:
            await self.qbt_client.rename_folder(qbt_hash, old_folder, new_folder)
