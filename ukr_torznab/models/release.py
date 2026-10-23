import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, overload

from ukr_torznab.models.aspect_ratio import AspectRatio
from ukr_torznab.models.audio_source import AudioSource
from ukr_torznab.models.audio_type import AudioType
from ukr_torznab.models.codec_family import CodecFamily
from ukr_torznab.models.content_type import ContentType
from ukr_torznab.models.language import Lang
from ukr_torznab.models.quality import Quality
from ukr_torznab.models.resolution import Resolution
from ukr_torznab.models.tracker import Tracker
from ukr_torznab.models.video_format import VideoFormat

_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize(name: str) -> str:
    return _UNSAFE_RE.sub("", name).strip()


def _decode_json(raw):
    if raw is None or raw == "":
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None
    return raw


@overload
def enum_from_value[E: Enum](cls: type[E], v, *, default: E) -> E: ...
@overload
def enum_from_value[E: Enum](cls: type[E], v, *, default: None = None) -> E | None: ...
def enum_from_value[E: Enum](cls: type[E], v, *, default: E | None = None) -> E | None:
    if v is None or v == "":
        return default
    try:
        return cls(v)
    except ValueError:
        return default


def _parse_enum_list[E: Enum](raw, convert: Callable[[Any], E]) -> list[E]:
    decoded = _decode_json(raw)
    if not isinstance(decoded, list):
        return []
    out: list[E] = []
    for v in decoded:
        try:
            out.append(convert(v))
        except (KeyError, ValueError):
            continue
    return out


def parse_audio_types(raw) -> list[AudioType]:
    return _parse_enum_list(raw, AudioType)


def parse_audio_sources(raw) -> list[AudioSource]:
    # Stored by member name, not value (AudioSource values are auto()).
    return _parse_enum_list(raw, AudioSource.__getitem__)


def parse_langs(raw) -> list[Lang]:
    return _parse_enum_list(raw, Lang)


def parse_file_to_episode(raw) -> dict[str, list[int]] | None:
    decoded = _decode_json(raw)
    if not isinstance(decoded, dict):
        return None
    return {str(k): list(v) for k, v in decoded.items()}


_STATUS_DVF: dict[str, str] = {
    "gold": "0",
    "author": "0",
    "silver": "0.5",
    "bronze": "0.75",
}


@dataclass(slots=True, kw_only=True)
class Release:
    id: int
    tracker: Tracker
    name: str
    content_type: ContentType
    title: str
    year: int | None = None
    imdb_id: int | None = None
    tvdb_id: int | None = None
    tmdb_id: int | None = None

    season: int
    min_episode: int | None = None
    max_episode: int | None = None
    season_complete: bool | None = None
    file_to_episode: dict[str, list[int]] | None = None

    torrent_size: int | None = None
    quality: Quality = Quality.UNKNOWN
    resolution: Resolution = Resolution.UNKNOWN
    codec: CodecFamily = CodecFamily.UNKNOWN
    hdr: VideoFormat = VideoFormat.SDR
    cut: str | None = None
    ratio: AspectRatio = AspectRatio.STANDARD
    hybrid: bool = False

    audio_types: list[AudioType] = field(default_factory=list)
    audio_sources: list[AudioSource] = field(default_factory=list)
    audio_lang: list[Lang] = field(default_factory=list)
    subtitle_lang: list[Lang] = field(default_factory=list)

    release_group: str | None = None
    author: str | None = None
    registered_at: datetime

    seeders: int = 0
    leechers: int = 0

    download_link: str
    details_link: str
    grabs: int | None = None
    download_volume_factor: str
    upload_volume_factor: str | None = None
    minimum_ratio: str | None = None
    minimum_seedtime: str | None = None
    seedtype: str | None = None

    infohash_sha256: str | None = None

    @classmethod
    def from_db_row(cls, row) -> "Release":
        m = row._mapping if hasattr(row, "_mapping") else row

        min_episode = max_episode = None
        season = m.get("season", 1)
        file_to_episode = parse_file_to_episode(m.get("file_to_episode"))
        season_complete = m.get("season_complete")
        if file_to_episode and not season_complete:
            eps = [v[1] for v in file_to_episode.values() if v[0] == season]
            if eps:
                min_episode, max_episode = min(eps), max(eps)

        return cls(
            id=int(m["id"]),
            tracker=Tracker.toloka,
            name=m.get("name") or "",
            content_type=ContentType(m["content_type"]),
            title=m.get("title"),
            year=m.get("year"),
            imdb_id=m.get("imdb_id"),
            tvdb_id=m.get("tvdb_id"),
            tmdb_id=m.get("tmdb_id"),
            season=season,
            min_episode=min_episode,
            max_episode=max_episode,
            season_complete=season_complete,
            file_to_episode=file_to_episode,
            torrent_size=m.get("torrent_size"),
            quality=enum_from_value(Quality, m.get("quality"), default=Quality.UNKNOWN),
            resolution=enum_from_value(Resolution, m.get("resolution"), default=Resolution.UNKNOWN),
            codec=enum_from_value(CodecFamily, m.get("codec"), default=CodecFamily.UNKNOWN),
            hdr=enum_from_value(VideoFormat, m.get("hdr"), default=VideoFormat.SDR),
            cut=m.get("cut"),
            ratio=enum_from_value(AspectRatio, m.get("ratio"), default=AspectRatio.STANDARD),
            hybrid=bool(m.get("hybrid") or False),
            audio_types=parse_audio_types(m.get("audio_types")),
            audio_sources=parse_audio_sources(m.get("audio_sources")),
            audio_lang=parse_langs(m.get("audio_lang")),
            subtitle_lang=parse_langs(m.get("subtitle_lang")),
            release_group=m.get("release_group"),
            author=m.get("author"),
            registered_at=m.get("registered_at"),
            seeders=m.get("seeders") or 0,
            leechers=m.get("leechers") or 0,
            details_link=f"https://toloka.to/t{m['id']}",
            download_link=f"download/{m['download_id']}",
            download_volume_factor=_STATUS_DVF.get(m.get("status"), "1"),
            minimum_ratio="0.15",
            seedtype="ratio",
            infohash_sha256=m.get("infohash_sha256"),
        )

    @property
    def is_tv(self):
        return self.content_type is ContentType.TV

    def release_name_parts(
        self,
        *,
        season: int | None = None,
        episode: int | None = None,
        end_episode: int | None = None,
        release_id: int | None = None,
    ) -> list[str]:
        parts: list[str | None] = [_sanitize(self.title)]

        if self.content_type is ContentType.TV:
            if episode is not None and end_episode is not None and end_episode != episode:
                parts.append(f"S{season:02d}E{episode:02d}-{end_episode:02d}")
            elif episode is not None:
                parts.append(f"S{season:02d}E{episode:02d}")
            else:
                parts.append(f"S{season:02d}")

        if self.content_type is ContentType.MOVIE:
            parts.append(str(self.year or 1800))

        parts.append(self.cut)

        parts.append(str(self.ratio))

        if self.hybrid:
            parts.append("Hybrid")

        if self.resolution is not Resolution.UNKNOWN:
            parts.append(self.resolution.value)

        parts.append(str(self.quality))
        if self.quality is not Quality.BR_DISK:
            parts.append(str(self.codec))

        if self.hdr is not VideoFormat.SDR:
            parts.append(self.hdr.value.upper().replace("-", " "))

        audio = ".".join(tag for tag in (str(t) for t in self.audio_types) if tag)
        parts.append(audio)

        locale = ".".join(tag for tag in (str(lang) for lang in self.audio_lang) if tag)
        parts.append(locale)

        subs = ".".join(f"sub{c}" for c in (lang.code() for lang in self.subtitle_lang) if c)
        parts.append(subs)

        studio = ".".join(tag for tag in (str(src) for src in self.audio_sources) if tag)
        parts.append(studio)

        if release_id is not None:
            parts.append(f"[{release_id}]")

        return [p for p in parts if p]

    def group_tag(self) -> str:
        g = self.release_group or self.author or ""
        return re.sub(r"[^0-9a-z]", "", g.lower())

    def _with_group(self, parts: list[str], suffix: str = "") -> str:
        base = " ".join(parts)
        group = self.group_tag()
        return f"{base}-{group}{suffix}" if group else f"{base}{suffix}"

    def release_name(self, *, xseed: bool = False) -> str:
        parts = self.release_name_parts(
            season=self.season,
            episode=self.min_episode,
            end_episode=self.max_episode,
        )
        if xseed:
            return " ".join(parts) + "-"
        return self._with_group(parts)

    def movie_folder(self) -> str:
        return self._with_group(self.release_name_parts(release_id=self.id))

    def tv_folder(self) -> str:
        return self._with_group(self.release_name_parts(season=self.season, release_id=self.id))

    def episode_filename(self, season: int, episode: int, ext: str) -> str:
        return self._with_group(self.release_name_parts(season=season, episode=episode), ext)
