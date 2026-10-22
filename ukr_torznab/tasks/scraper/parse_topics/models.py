from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from ukr_torznab.models import (
    AspectRatio,
    AudioSource,
    AudioType,
    CodecFamily,
    ContentType,
    Lang,
    Quality,
    Resolution,
    VideoFormat,
)


class SkipReason(Enum):
    UNEXPECTED_PAGE_STRUCTURE = auto()
    INVALID_TORRENT = auto()
    DISALLOWED_FILE_EXTENSION = auto()
    NO_VIDEO_FILES = auto()
    NO_IMDB_LINK = auto()
    IMDB_NOT_IN_DATABASE = auto()
    TV_NO_SKYHOOK_METADATA = auto()
    MOVIE_NO_SERVARR_METADATA = auto()
    MOVIE_MULTIPLE_VIDEO_FILES = auto()
    INCONSISTENT_FOLDER_STRUCTURE = auto()
    CANNOT_DETERMINE_SEASON = auto()


@dataclass(frozen=True, slots=True)
class SkippedPage:
    page_id: int
    reason: SkipReason


@dataclass(slots=True)
class ParsedPage:
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
