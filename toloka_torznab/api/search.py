"""Search parameter parsing and RSS feed builder."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import format_datetime
from types import SimpleNamespace

from fastapi.responses import Response
from lxml import etree

from toloka_torznab.naming import release_name

from .xml import _CAT_MOVIE, _CAT_TV, _CT_RSS, _CT_TORRENT, torznab_attr, xml_response


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
            if c == _CAT_TV or c.startswith("50"):
                types.add("tv")
            elif c == _CAT_MOVIE or c.startswith("20"):
                types.add("movie")
    return list(types) if types else None


def build_rss(rows, base_url: str) -> Response:
    from .xml import _TORZNAB_NS  # local to avoid circular at module level

    rss = etree.Element("rss", nsmap={"torznab": _TORZNAB_NS})
    rss.set("version", "2.0")
    channel = etree.SubElement(rss, "channel")

    title_el = etree.SubElement(channel, "title")
    title_el.text = "Toloka Torznab"

    for row in rows:
        item = etree.SubElement(channel, "item")

        t = etree.SubElement(item, "title")
        t.text = release_name(row)

        guid_el = etree.SubElement(item, "guid")
        guid_el.set("isPermaLink", "false")
        guid_el.text = f"toloka-{row.id}"

        comments_el = etree.SubElement(item, "comments")
        comments_el.text = f"https://toloka.to/t{row.id}"

        dt = row.registered_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        pub = etree.SubElement(item, "pubDate")
        pub.text = format_datetime(dt)

        cat_id = _CAT_TV if row.content_type == "tv" else _CAT_MOVIE
        cat_el = etree.SubElement(item, "category")
        cat_el.text = cat_id

        size = row.torrent_size or 0
        size_el = etree.SubElement(item, "size")
        size_el.text = str(size)

        enc = etree.SubElement(item, "enclosure")
        enc.set("url", f"{base_url}/download/{row.download_id}")
        enc.set("length", str(size))
        enc.set("type", _CT_TORRENT)

        torznab_attr(item, "seeders", str(row.seeders))
        torznab_attr(item, "leechers", str(row.leechers))
        torznab_attr(item, "peers", str(row.seeders + row.leechers))

        if row.infohash_sha256:
            torznab_attr(item, "infohash", row.infohash_sha256)
        if row.imdb_id:
            torznab_attr(item, "imdbid", f"tt{row.imdb_id:07d}")
        if row.content_type == "tv":
            if row.tvdb_id:
                torznab_attr(item, "tvdbid", str(row.tvdb_id))
            if row.season is not None:
                torznab_attr(item, "season", str(row.season))
        elif row.content_type == "movie":
            if row.tmdb_id:
                torznab_attr(item, "tmdbid", str(row.tmdb_id))
        if row.quality:
            torznab_attr(item, "quality", row.quality)
        if row.resolution:
            torznab_attr(item, "resolution", row.resolution)

    return xml_response(rss, _CT_RSS)


def build_utp_rss(items: list[dict], base_url: str) -> Response:
    """Build Torznab RSS feed from transformed UTP items."""
    from .xml import _TORZNAB_NS

    rss = etree.Element("rss", nsmap={"torznab": _TORZNAB_NS})
    rss.set("version", "2.0")
    channel = etree.SubElement(rss, "channel")

    title_el = etree.SubElement(channel, "title")
    title_el.text = "UTP Torznab"

    for item in items:
        row = SimpleNamespace(**item)
        el = etree.SubElement(channel, "item")

        t = etree.SubElement(el, "title")
        t.text = release_name(row)

        guid_el = etree.SubElement(el, "guid")
        guid_el.set("isPermaLink", "false")
        guid_el.text = f"utp-{item['id']}"

        if item.get("details_link"):
            comments_el = etree.SubElement(el, "comments")
            comments_el.text = item["details_link"]

        if item.get("created_at"):
            try:
                dt = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                pub = etree.SubElement(el, "pubDate")
                pub.text = format_datetime(dt)
            except (ValueError, AttributeError):
                pass

        cat_id = _CAT_TV if item["content_type"] == "tv" else _CAT_MOVIE
        cat_el = etree.SubElement(el, "category")
        cat_el.text = cat_id

        size = item.get("size") or 0
        size_el = etree.SubElement(el, "size")
        size_el.text = str(size)

        enc = etree.SubElement(el, "enclosure")
        enc.set("url", item["download_link"])
        enc.set("length", str(size))
        enc.set("type", _CT_TORRENT)

        torznab_attr(el, "seeders", str(item.get("seeders", 0)))
        torznab_attr(el, "leechers", str(item.get("leechers", 0)))
        torznab_attr(el, "peers", str(item.get("seeders", 0) + item.get("leechers", 0)))

        if item.get("info_hash"):
            torznab_attr(el, "infohash", item["info_hash"])
        if item.get("imdb_id"):
            torznab_attr(el, "imdbid", f"tt{item['imdb_id']:07d}")
        if item["content_type"] == "tv":
            if item.get("tvdb_id"):
                torznab_attr(el, "tvdbid", str(item["tvdb_id"]))
            if item.get("season") is not None:
                torznab_attr(el, "season", str(item["season"]))
        elif item["content_type"] == "movie":
            if item.get("tmdb_id"):
                torznab_attr(el, "tmdbid", str(item["tmdb_id"]))
        if item.get("quality"):
            torznab_attr(el, "quality", item["quality"])
        if item.get("resolution"):
            torznab_attr(el, "resolution", item["resolution"])

    return xml_response(rss, _CT_RSS)
