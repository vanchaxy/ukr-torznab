"""JSON views of parser output, used by the browser extension (`/toloka/info`, `/utp/info`)."""

import json
import os
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from ukr_torznab.clients.utp import build_file_to_episode
from ukr_torznab.clients.utp.client import transform_utp_item
from ukr_torznab.clients.utp.parser import parse_mediainfo, parse_track_details
from ukr_torznab.db.queries import PARSER_VERSION
from ukr_torznab.models import (
    AudioType,
    ContentType,
    Lang,
    Quality,
    Release,
    Resolution,
)
from ukr_torznab.settings import TOLOKA_CATEGORIES


def _label(e: Enum) -> str:
    return str(e) or str(e.value)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def release_to_json(rel: Release) -> dict[str, Any]:
    out: dict[str, Any] = {
        "tracker": rel.tracker.value,
        "id": rel.id,
        "name": rel.name,
        "release_name": rel.release_name(),
        "xseed_name": rel.release_name(xseed=True),
        "folder": rel.tv_folder() if rel.is_tv else rel.movie_folder(),
        "content_type": rel.content_type.value,
        "title": rel.title,
        "year": rel.year,
        "imdb_id": f"tt{rel.imdb_id:07d}" if rel.imdb_id else None,
        "tvdb_id": rel.tvdb_id,
        "tmdb_id": rel.tmdb_id,
        "season": rel.season if rel.is_tv else None,
        "min_episode": rel.min_episode,
        "max_episode": rel.max_episode,
        "season_complete": rel.season_complete,
        "torrent_size": rel.torrent_size,
        "quality": _label(rel.quality),
        "resolution": rel.resolution.value,
        "codec": _label(rel.codec),
        "hdr": rel.hdr.value,
        "cut": rel.cut,
        "ratio": rel.ratio.value,
        "hybrid": rel.hybrid,
        "audio_types": [_label(t) for t in rel.audio_types],
        "audio_sources": [_label(s) for s in rel.audio_sources],
        "audio_lang": [_label(lang) for lang in rel.audio_lang],
        "subtitle_lang": [_label(lang) for lang in rel.subtitle_lang],
        "release_group": rel.release_group,
        "author": rel.author,
        "registered_at": _iso(rel.registered_at),
        "seeders": rel.seeders,
        "leechers": rel.leechers,
        "details_link": rel.details_link,
        "warnings": release_warnings(rel),
    }
    if rel.is_tv and rel.file_to_episode:
        out["episodes"] = [
            {
                "file": path,
                "season": season,
                "episode": episode,
                "renamed": rel.episode_filename(season, episode, os.path.splitext(path)[1]),
            }
            for path, (season, episode) in sorted(
                rel.file_to_episode.items(),
                key=lambda kv: (kv[1][0], kv[1][1], kv[0]),
            )
        ]
    return out


def release_warnings(rel: Release) -> list[str]:
    """Things that make a parsed release harder for Sonarr/Radarr to match or rank."""
    warnings: list[str] = []
    if not rel.imdb_id:
        warnings.append("No IMDb id")
    if rel.content_type is ContentType.TV and not rel.tvdb_id:
        warnings.append("No TVDB id")
    if rel.content_type is ContentType.MOVIE and not rel.tmdb_id:
        warnings.append("No TMDB id")
    if rel.quality is Quality.UNKNOWN:
        warnings.append("Unknown quality")
    if rel.resolution is Resolution.UNKNOWN:
        warnings.append("Unknown resolution")
    if not rel.audio_types or AudioType.UNKNOWN in rel.audio_types:
        warnings.append("Unknown audio type")
    if Lang.UKRAINIAN not in rel.audio_lang:
        warnings.append("No Ukrainian audio")
    return warnings


def toloka_topic_info(topic_id: int, row) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": topic_id,
        "tracked_categories": TOLOKA_CATEGORIES,
        "parser_version": PARSER_VERSION,
    }
    if row is None:
        out["state"] = "not_indexed"
        return out

    out["topic"] = {
        "name": row.name,
        "category": row.category,
        "status": row.status,
        "added_on": row.added_on.isoformat(),
        "updated_at": _iso(row.updated_at),
        "observed_at": _iso(row.observed_at),
        "stale": not row.searchable,
        "downloaded_at": _iso(row.downloaded_at),
    }

    # In Electric consumer mode there are no pages: topic and release rows arrive pre-parsed.
    has_page = bool(row.has_html) and bool(row.has_torrent)
    if row.release_id is None:
        out["state"] = "pending" if has_page else "not_downloaded"
        return out

    out["state"] = "ok" if row.result == "ok" else "skipped"
    out["reason"] = None if row.result == "ok" else row.result
    out["parsed_at"] = _iso(row.parsed_at)
    out["release_parser_version"] = row.parser_version
    out["reparse_pending"] = has_page and (
        (row.downloaded_at is not None and row.downloaded_at > row.parsed_at)
        or (row.parser_version or 0) < PARSER_VERSION
    )
    if row.result == "ok":
        release = release_to_json(Release.from_db_row(row))
        release["video_files"] = json.loads(row.video_files) if row.video_files else []
        release["last_episode"] = row.last_episode
        release["acodec"] = row.acodec
        release["hash_changed_at"] = _iso(row.hash_changed_at)
        out["release"] = release
    return out


def utp_item_info(item: dict) -> dict[str, Any]:
    attrs = item["attributes"]
    rel = transform_utp_item(item)
    files = attrs.get("files") or []
    if rel.is_tv:
        # Same mapping the renamer builds for UTP season packs.
        rel.file_to_episode = build_file_to_episode(rel.season, files)
    out = release_to_json(rel)
    out["utp"] = {
        "category": attrs.get("category"),
        "type": attrs.get("type"),
        "resolution": attrs.get("resolution"),
    }
    mi_text = attrs.get("media_info")
    out["audio_tracks"] = parse_track_details(parse_mediainfo(mi_text)) if mi_text else []
    out["files"] = [f.get("name") for f in files]
    return out
