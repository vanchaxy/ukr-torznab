from __future__ import annotations

import re

from lxml.etree import _Element

_IMDB_PATTERN = re.compile(r"imdb.*(tt\d+)")


def extract_imdb(dom: _Element) -> str | None:
    """Extract a single IMDB id (e.g. ``"tt0123456"``) from the page DOM.

    Tries the "official" badge link first (``<a>`` wrapping an IMDB ``<img>``),
    then falls back to *any* IMDB-containing href/src in the post body.

    Returns ``None`` when no unambiguous IMDB id can be found.
    """
    # Strategy 1: <a href="…imdb…"><img src="…imdb…"></a>  (the "main" badge)
    main_hrefs = dom.xpath(
        './/span[@class="postbody"]'
        '/a[contains(@href, "imdb")]'
        '/img[contains(@src, "imdb")]'
        "/../@href",
    )
    main_ids = _extract_ids(main_hrefs)
    if main_ids:
        return main_ids[0]

    # Strategy 2: any imdb link or image in the post body
    extra_hrefs = dom.xpath(
        './/span[@class="postbody"]//a[contains(@href, "imdb")]/@href',
    )
    extra_srcs = dom.xpath(
        './/span[@class="postbody"]//img[contains(@src, "imdb")]/@src',
    )
    extra_ids = _extract_ids(list(extra_hrefs) + list(extra_srcs))

    if not extra_ids:
        return None

    # Accept only when all refs agree, or there's a single video file
    if len(set(extra_ids)) == 1:
        return extra_ids[0]

    return None


def extract_imdb_multi(dom: _Element, single_file: bool) -> str | None:
    """Like extract_imdb but also accepts ambiguous refs when
    the torrent contains only one video file.
    """
    result = extract_imdb(dom)
    if result is not None:
        return result

    # Re-try the fallback allowing ambiguity for single-file torrents
    extra_hrefs = dom.xpath(
        './/span[@class="postbody"]//a[contains(@href, "imdb")]/@href',
    )
    extra_srcs = dom.xpath(
        './/span[@class="postbody"]//img[contains(@src, "imdb")]/@src',
    )
    extra_ids = _extract_ids(list(extra_hrefs) + list(extra_srcs))

    if extra_ids and single_file:
        return extra_ids[0]
    return None


def _extract_ids(raw_urls: list[str]) -> list[str]:
    ids: list[str] = []
    for url in raw_urls:
        m = _IMDB_PATTERN.search(url)
        if m and int(m.group(1)[2:]):
            ids.append(m.group(1))
    return ids
