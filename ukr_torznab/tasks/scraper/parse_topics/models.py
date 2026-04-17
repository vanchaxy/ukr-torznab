from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ukr_torznab.enums import (
    AspectRatio,
    AudioSource,
    AudioType,
    CodecFamily,
    ContentType,
    Lang,
    Quality,
    Resolution,
    SkipReason,
    VideoFormat,
)


@dataclass(frozen=True, slots=True)
class SkippedPage:
    """A page that was examined but not included in the dataset."""

    page_id: int
    reason: SkipReason


@dataclass(slots=True)
class ParsedPage:
    """All structured metadata extracted from a single Toloka torrent page."""

    page_id: int
    imdb_id: int
    title: str  # primary_title from IMDB, falling back to original_title
    year: int | None
    name: str
    content_type: ContentType
    video_files: list[Path]
    registered_at: datetime  # UTC

    # Movie-specific
    tmdb_id: int | None = None

    # TV-specific
    season: int | None = None
    tvdb_id: int | None = None
    file_to_episode: dict[str, tuple[int, int]] | None = None
    season_complete: bool | None = None
    video_files_hash: str | None = None  # sha256 of video_files at mapping time

    # Media metadata (best-effort, may be UNKNOWN)
    quality: Quality = Quality.UNKNOWN
    resolution: Resolution = Resolution.UNKNOWN
    codec: CodecFamily = CodecFamily.UNKNOWN
    audio_types: set[AudioType] = field(default_factory=lambda: {AudioType.UNKNOWN})
    audio_sources: set[AudioSource] = field(default_factory=set)
    audio_lang: set[Lang] = field(default_factory=set)
    subtitle_lang: set[Lang] = field(default_factory=set)
    hdr: VideoFormat = VideoFormat.SDR
    cut: str | None = None
    ratio: AspectRatio = AspectRatio.STANDARD
    hybrid: bool = False

    # Authorship / release
    author: str | None = None
    release_group: str | None = None

    last_episode: int | None = None  # max episode number in this release for the stored season

    torrent_size: int | None = None  # total size in bytes from lt.torrent_info
    infohash_sha256: str | None = None  # sha256 of torrent infohash bytes

    acodec: str | None = None

    # Change detection
    content_hash: str | None = None  # sha256 of all other fields
