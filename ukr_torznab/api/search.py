"""Search parameter parsing and RSS feed builder."""

from __future__ import annotations

import json
from datetime import UTC
from email.utils import format_datetime

from fastapi.responses import Response
from lxml import etree

from ukr_torznab.api.caps import CAT_MOVIE, CAT_TV
from ukr_torznab.api.xml import _TORZNAB_NS, torznab_attr, xml_response
from ukr_torznab.naming import _CODEC_MAP_BY_VALUE, _LANG_DISPLAY_BY_VALUE, release_name

_TOLOKA_DVF: dict[str, str] = {
    "gold": "0",
    "author": "0",
    "silver": "0.5",
    "bronze": "0.75",
}


def _freeleech_dvf(value) -> str | None:
    """Convert freeleech value (e.g. '100%', '75%') to downloadvolumefactor string."""
    if not value or value is False:
        return None
    if isinstance(value, str) and value.endswith("%"):
        pct = float(value[:-1])
        result = round(1.0 - pct / 100.0, 4)
        return f"{result:.4f}".rstrip("0").rstrip(".")
    return None


def _langs_str(json_field) -> str | None:
    """Parse a JSON lang list (stored as Lang.value strings) to display names."""
    if not json_field:
        return None
    try:
        vals = json.loads(json_field) if isinstance(json_field, str) else json_field
        names = [_LANG_DISPLAY_BY_VALUE[v] for v in vals if v in _LANG_DISPLAY_BY_VALUE]
        return ", ".join(names) if names else None
    except (ValueError, TypeError):
        return None


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


def build_rss(items: list[dict], *, source: str, xseed: bool = False) -> Response:
    channel_title = "Toloka Torznab" if source == "toloka" else "UTP Torznab"

    rss = etree.Element("rss", nsmap={"torznab": _TORZNAB_NS})
    rss.set("version", "2.0")
    channel = etree.SubElement(rss, "channel")
    etree.SubElement(channel, "title").text = channel_title

    for item in items:
        el = etree.SubElement(channel, "item")

        etree.SubElement(el, "title").text = release_name(item, xseed=xseed)

        guid_el = etree.SubElement(el, "guid")
        guid_el.set("isPermaLink", "false")
        guid_el.text = f"{source}-{item['id']}"

        comments_el = etree.SubElement(el, "comments")
        comments_el.text = item.get("details_link") or f"https://toloka.to/t{item['id']}"

        dt = item.get("registered_at")
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            etree.SubElement(el, "pubDate").text = format_datetime(dt)

        cat_id = CAT_TV if item["content_type"] == "tv" else CAT_MOVIE
        etree.SubElement(el, "category").text = cat_id

        size = item.get("torrent_size") or 0
        etree.SubElement(el, "size").text = str(size)

        enc = etree.SubElement(el, "enclosure")
        enc.set("url", item.get("download_link") or f"download/{item['download_id']}")
        enc.set("length", str(size))
        enc.set("type", "application/x-bittorrent")

        torznab_attr(el, "seeders", str(item.get("seeders") or 0))
        torznab_attr(el, "leechers", str(item.get("leechers") or 0))
        torznab_attr(el, "peers", str((item.get("seeders") or 0) + (item.get("leechers") or 0)))

        if item.get("grabs") is not None:
            torznab_attr(el, "grabs", str(item["grabs"]))

        if item.get("imdb_id"):
            torznab_attr(el, "imdbid", str(item["imdb_id"]))

        if item["content_type"] == "tv":
            if item.get("tvdb_id"):
                torznab_attr(el, "tvdbid", str(item["tvdb_id"]))
            if item.get("season") is not None:
                torznab_attr(el, "season", str(item["season"]))
            if item.get("last_episode") is not None and not item.get("season_complete"):
                torznab_attr(el, "episode", str(item["last_episode"]))
        elif item["content_type"] == "movie":
            if item.get("tmdb_id"):
                torznab_attr(el, "tmdbid", str(item["tmdb_id"]))

        if item.get("year"):
            torznab_attr(el, "year", str(item["year"]))
        if item.get("quality"):
            torznab_attr(el, "quality", item["quality"])
        if item.get("resolution"):
            torznab_attr(el, "resolution", item["resolution"])
        if item.get("codec"):
            torznab_attr(el, "video", _CODEC_MAP_BY_VALUE.get(item["codec"], item["codec"]))

        lang_str = _langs_str(item.get("audio_lang"))
        if lang_str:
            torznab_attr(el, "language", lang_str)

        subs_str = _langs_str(item.get("subtitle_lang"))
        if subs_str:
            torznab_attr(el, "subs", subs_str)

        if item.get("release_group"):
            torznab_attr(el, "team", item["release_group"])
        if item.get("author"):
            torznab_attr(el, "poster", item["author"])

        if source == "toloka":
            torznab_attr(el, "minimumratio", "0.15")
            torznab_attr(el, "seedtype", "ratio")
            dvf = _TOLOKA_DVF.get(item.get("status") or "")
            if dvf is not None:
                torznab_attr(el, "downloadvolumefactor", dvf)
        elif source == "utp":
            torznab_attr(el, "minimumratio", "0.4")
            torznab_attr(el, "minimumseedtime", "259200")
            torznab_attr(el, "seedtype", "both")
            dvf = _freeleech_dvf(item.get("freeleech"))
            if dvf is not None:
                torznab_attr(el, "downloadvolumefactor", dvf)
            torznab_attr(
                el,
                "uploadvolumefactor",
                "2" if item.get("double_upload") or item.get("featured") else "1",
            )

    return xml_response(rss, "application/rss+xml; charset=utf-8")
