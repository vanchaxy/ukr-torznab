import logging
from datetime import UTC, datetime

import httpx
from httpx_limiter import AsyncRateLimitedTransport, Rate
from httpx_limiter.aiolimiter import AiolimiterAsyncLimiter

from ukr_torznab.clients.utp.parser import (
    parse_audio_tracks,
    parse_mediainfo,
    parse_release,
    parse_subtitle_langs,
)
from ukr_torznab.models import (
    AspectRatio,
    AudioSource,
    AudioType,
    ContentType,
    Lang,
    Release,
    Tracker,
)

log = logging.getLogger(__name__)


def dvf(freeleech) -> str:
    if not freeleech or freeleech is False:
        return "1"
    if isinstance(freeleech, str) and freeleech.endswith("%"):
        pct = float(freeleech[:-1])
        result = round(1.0 - pct / 100.0, 4)
        return f"{result:.4f}".rstrip("0").rstrip(".")
    return "1"


class UtpClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url="https://utp.to/api/torrents",
            timeout=30,
            transport=AsyncRateLimitedTransport.create(
                AiolimiterAsyncLimiter.create(Rate.create(1, 1)),
            ),
        )

    async def search(
        self,
        *,
        name: str | None = None,
        imdb_id: int | None = None,
        tvdb_id: int | None = None,
        tmdb_id: int | None = None,
        categories: list[int] | None = None,
        season: int | None = None,
        episode: int | None = None,
        per_page: int = 100,
        page: int = 1,
    ) -> list[Release]:
        params: dict[str, str] = {
            "api_token": self._api_key,
            "perPage": str(per_page),
            "page": str(page),
        }
        if name:
            params["name"] = name
        if imdb_id is not None:
            params["imdbId"] = str(imdb_id)
        if tvdb_id is not None:
            params["tvdbId"] = str(tvdb_id)
        if tmdb_id is not None:
            params["tmdbId"] = str(tmdb_id)
        if season is not None:
            params["seasonNumber"] = str(season)
        if episode is not None:
            params["episodeNumber"] = str(episode)
        if categories:
            for i, cat_id in enumerate(categories):
                params[f"categories[{i}]"] = str(cat_id)

        try:
            resp = await self._client.get("/filter", params=params)
            resp.raise_for_status()
            data = resp.json()
            return [transform_utp_item(it) for it in data.get("data", [])]
        except httpx.HTTPError:
            log.exception("UTP API request failed")
            return []

    async def get_by_id(self, torrent_id: str) -> Release | None:
        try:
            resp = await self._client.get(f"/{torrent_id}", params={"api_token": self._api_key})
            resp.raise_for_status()
            return transform_utp_item(resp.json())
        except httpx.HTTPError:
            log.exception("UTP get_by_id failed for id=%s", torrent_id)
            return None

    async def close(self) -> None:
        await self._client.aclose()


def transform_utp_item(item: dict) -> Release:
    attrs = item["attributes"]
    is_tv = attrs["category"] == "TV"

    release = parse_release(
        attrs["name"],
        attrs["type"],
        attrs["resolution"],
        attrs["files"],
        is_tv,
    )

    audio_types: list[AudioType] = []
    audio_sources: list[AudioSource] = []
    audio_langs: list[Lang] = []
    subtitle_langs: list[Lang] = []

    mi_text = attrs.get("media_info")
    if mi_text:
        mi = parse_mediainfo(mi_text)
        audio_types, audio_sources, audio_langs = parse_audio_tracks(mi)
        subtitle_langs = parse_subtitle_langs(mi)

    registered_at = None
    created_at_str = attrs.get("created_at")
    if created_at_str:
        try:
            registered_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            registered_at = datetime(1970, 1, 1, tzinfo=UTC)

    return Release(
        id=int(item["id"]),
        tracker=Tracker.utopia,
        name=attrs["name"],
        title=release["title"],
        year=release["year"],
        content_type=ContentType.TV if is_tv else ContentType.MOVIE,
        season=release["season"],
        min_episode=release["min_episode"],
        max_episode=release["max_episode"],
        season_complete=release["season_complete"],
        quality=release["quality"],
        resolution=release["resolution"],
        codec=release["codec"],
        hdr=release["hdr"],
        cut=release["cut"],
        ratio=release["ratio"] or AspectRatio.STANDARD,
        hybrid=release["hybrid"],
        release_group=release["group"],
        author=attrs.get("uploader"),
        imdb_id=attrs.get("imdb_id"),
        tvdb_id=attrs.get("tvdb_id"),
        tmdb_id=attrs.get("tmdb_id"),
        torrent_size=attrs.get("size", 0),
        seeders=attrs.get("seeders", 0),
        leechers=attrs.get("leechers", 0),
        download_link=attrs.get("download_link"),
        details_link=attrs.get("details_link"),
        registered_at=registered_at,
        grabs=attrs.get("times_completed", 0),
        download_volume_factor=dvf(attrs.get("freeleech")),
        upload_volume_factor="2" if attrs.get("double_upload") or attrs.get("featured") else "1",
        minimum_ratio="0.4",
        minimum_seedtime="259200",
        seedtype="both",
        audio_types=audio_types,
        audio_sources=audio_sources,
        audio_lang=audio_langs,
        subtitle_lang=subtitle_langs,
    )
