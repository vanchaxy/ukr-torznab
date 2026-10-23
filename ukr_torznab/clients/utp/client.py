import logging
from datetime import datetime

import httpx
from httpx_limiter import Rate

from ukr_torznab.clients._http import make_client
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
from ukr_torznab.utils import EPOCH

logger = logging.getLogger(__name__)


def _download_volume_factor(freeleech) -> str:
    if not freeleech:
        return "1"
    if isinstance(freeleech, str) and freeleech.endswith("%"):
        pct = float(freeleech[:-1])
        result = round(1.0 - pct / 100.0, 4)
        return f"{result:.4f}".rstrip("0").rstrip(".")
    return "1"


class UtpClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = make_client(
            "https://utp.to/api/torrents",
            rate=Rate.create(1, 1),
            timeout=30,
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
        if season is not None:
            params["seasonNumber"] = str(season)
        if episode is not None:
            params["episodeNumber"] = str(episode)
        if categories:
            for i, cat_id in enumerate(categories):
                params[f"categories[{i}]"] = str(cat_id)

        # UTP ANDs id filters, and many torrents there lack a tvdb (or imdb) id. Sonarr sends
        # tvdbid and imdbid together, so query each id on its own and merge the results.
        id_filters = [
            {key: str(value)}
            for key, value in (("imdbId", imdb_id), ("tvdbId", tvdb_id), ("tmdbId", tmdb_id))
            if value is not None
        ] or [{}]

        releases: dict[int, Release] = {}
        for id_filter in id_filters:
            for rel in await self._filter(params | id_filter):
                releases.setdefault(rel.id, rel)
        # The requested ids all point at the same title, so fill in the ones UTP is missing.
        for rel in releases.values():
            rel.imdb_id = rel.imdb_id or imdb_id
            rel.tvdb_id = rel.tvdb_id or tvdb_id
            rel.tmdb_id = rel.tmdb_id or tmdb_id
        return list(releases.values())

    async def _filter(self, params: dict[str, str]) -> list[Release]:
        try:
            resp = await self._client.get("/filter", params=params)
            resp.raise_for_status()
            data = resp.json()
            return [transform_utp_item(it) for it in data.get("data", [])]
        except httpx.HTTPError:
            logger.exception("UTP API request failed")
            return []

    async def get_by_id(self, torrent_id: str) -> Release | None:
        item = await self.get_item(torrent_id)
        return transform_utp_item(item) if item is not None else None

    async def get_item(self, torrent_id: str) -> dict | None:
        """The raw API item, for callers that need more than the parsed `Release`."""
        try:
            resp = await self._client.get(f"/{torrent_id}", params={"api_token": self._api_key})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            logger.exception("UTP get_by_id failed for id=%s", torrent_id)
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

    registered_at = EPOCH
    created_at_str = attrs.get("created_at")
    if created_at_str:
        try:
            registered_at = datetime.fromisoformat(created_at_str)
        except (ValueError, AttributeError):
            pass

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
        download_volume_factor=_download_volume_factor(attrs.get("freeleech")),
        upload_volume_factor="2" if attrs.get("double_upload") or attrs.get("featured") else "1",
        minimum_ratio="0.4",
        minimum_seedtime="259200",
        seedtype="both",
        audio_types=audio_types,
        audio_sources=audio_sources,
        audio_lang=audio_langs,
        subtitle_lang=subtitle_langs,
    )
