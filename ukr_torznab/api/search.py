from dataclasses import dataclass
from datetime import UTC
from email.utils import format_datetime

from fastapi.responses import Response
from lxml import etree

from ukr_torznab.api.caps import CAT_MOVIE, CAT_TV, DEFAULT_LIMIT, MAX_LIMIT
from ukr_torznab.api.xml import _TORZNAB_NS, torznab_attr, xml_response
from ukr_torznab.models import (
    CodecFamily,
    ContentType,
    Lang,
    Quality,
    Release,
    Resolution,
)
from ukr_torznab.models.codec_family import CODEC_MAP

SEARCH_FUNCTIONS = ("search", "tvsearch", "movie")


@dataclass(frozen=True, slots=True)
class SearchParams:
    t: str
    q: str | None
    content_types: list[str] | None
    imdb_id: int | None
    tvdb_id: int | None
    tmdb_id: int | None
    season: int | None
    episode: int | None
    offset: int
    limit: int
    xseed: bool


def search_params(
    t: str = "search",
    q: str | None = None,
    cat: str | None = None,
    imdbid: str | None = None,
    tvdbid: str | None = None,
    tmdbid: str | None = None,
    season: int | None = None,
    ep: int | None = None,
    offset: int = 0,
    limit: int = DEFAULT_LIMIT,
    xseed: int = 0,
) -> SearchParams:
    """FastAPI dependency: parse and normalise the Torznab query string."""
    return SearchParams(
        t=t,
        q=q,
        content_types=content_type_filter(
            cat,
            force_tv=(t == "tvsearch"),
            force_movie=(t == "movie"),
        ),
        imdb_id=parse_imdbid(imdbid),
        tvdb_id=_parse_int_id(tvdbid),
        tmdb_id=_parse_int_id(tmdbid),
        season=season,
        episode=ep,
        offset=max(offset, 0),
        limit=min(max(limit, 1), MAX_LIMIT),
        xseed=bool(xseed),
    )


def _langs_str(langs: list[Lang]) -> str | None:
    names = [str(lang) for lang in langs if str(lang)]
    return ", ".join(names) if names else None


def _parse_int_id(raw: str | None) -> int | None:
    return int(raw) if raw and raw.isdigit() else None


def parse_imdbid(raw: str | None) -> int | None:
    if not raw:
        return None
    s = raw.lstrip("t")
    return int(s) if s.isdigit() else None


def content_type_filter(
    cat: str | None,
    *,
    force_tv: bool = False,
    force_movie: bool = False,
) -> list[str] | None:
    types: set[str] = set()
    if force_tv:
        types.add("tv")
    if force_movie:
        types.add("movie")
    if cat:
        for c in cat.split(","):
            c = c.strip()
            if c == CAT_TV or c.startswith("50"):
                types.add("tv")
            elif c == CAT_MOVIE or c.startswith("20"):
                types.add("movie")
    return list(types) if types else None


def build_rss(items: list[Release], *, title: str, xseed: bool = False) -> Response:
    rss = etree.Element("rss", nsmap={"torznab": _TORZNAB_NS})
    rss.set("version", "2.0")
    channel = etree.SubElement(rss, "channel")
    etree.SubElement(channel, "title").text = title

    for item in items:
        el = etree.SubElement(channel, "item")

        etree.SubElement(el, "title").text = item.release_name(xseed=xseed)

        comments_el = etree.SubElement(el, "comments")
        comments_el.text = item.details_link

        dt = item.registered_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        etree.SubElement(el, "pubDate").text = format_datetime(dt)

        cat_id = CAT_TV if item.content_type is ContentType.TV else CAT_MOVIE
        etree.SubElement(el, "category").text = cat_id

        size = item.torrent_size or 0
        etree.SubElement(el, "size").text = str(size)

        enc = etree.SubElement(el, "enclosure")
        enc.set("url", item.download_link)
        enc.set("length", str(size))
        enc.set("type", "application/x-bittorrent")

        torznab_attr(el, "seeders", str(item.seeders or 0))
        torznab_attr(el, "leechers", str(item.leechers or 0))
        torznab_attr(el, "peers", str((item.seeders or 0) + (item.leechers or 0)))

        if item.grabs is not None:
            torznab_attr(el, "grabs", str(item.grabs))

        if item.imdb_id:
            torznab_attr(el, "imdbid", str(item.imdb_id))

        if item.content_type is ContentType.TV:
            if item.tvdb_id:
                torznab_attr(el, "tvdbid", str(item.tvdb_id))
            if item.season is not None:
                torznab_attr(el, "season", str(item.season))
            if item.min_episode is not None and item.min_episode == item.max_episode:
                torznab_attr(el, "episode", str(item.min_episode))
        elif item.content_type is ContentType.MOVIE:
            if item.tmdb_id:
                torznab_attr(el, "tmdbid", str(item.tmdb_id))

        if item.year:
            torznab_attr(el, "year", str(item.year))
        if item.quality is not Quality.UNKNOWN:
            torznab_attr(el, "quality", item.quality.value)
        if item.resolution is not Resolution.UNKNOWN:
            torznab_attr(el, "resolution", item.resolution.value)
        if item.codec is not CodecFamily.UNKNOWN:
            torznab_attr(el, "video", CODEC_MAP.get(item.codec, item.codec.value))

        lang_str = _langs_str(item.audio_lang)
        if lang_str:
            torznab_attr(el, "language", lang_str)

        subs_str = _langs_str(item.subtitle_lang)
        if subs_str:
            torznab_attr(el, "subs", subs_str)

        if item.release_group:
            torznab_attr(el, "team", item.release_group)
        if item.author:
            torznab_attr(el, "poster", item.author)

        torznab_attr(el, "downloadvolumefactor", item.download_volume_factor)
        if item.upload_volume_factor is not None:
            torznab_attr(el, "uploadvolumefactor", item.upload_volume_factor)
        if item.minimum_ratio is not None:
            torznab_attr(el, "minimumratio", item.minimum_ratio)
        if item.minimum_seedtime is not None:
            torznab_attr(el, "minimumseedtime", item.minimum_seedtime)
        if item.seedtype is not None:
            torznab_attr(el, "seedtype", item.seedtype)

    return xml_response(rss, "application/rss+xml; charset=utf-8")
