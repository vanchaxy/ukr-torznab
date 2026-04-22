import re
from typing import cast

from lxml.etree import _Element

_IMDB_PATTERN = re.compile(r"imdb.*(tt\d+)")


def _extract_ids(raw_urls: list[str]) -> list[str]:
    ids: list[str] = []
    for url in raw_urls:
        m = _IMDB_PATTERN.search(url)
        if m and int(m.group(1)[2:]):
            ids.append(m.group(1))
    return ids


def extract_imdb(dom: _Element, single_file: bool) -> str | None:
    # Strategy 1: <a href="…imdb…"><img src="…imdb…"></a>  (the "main" badge)
    main_hrefs = cast(
        "list[str]",
        dom.xpath(
            './/span[@class="postbody"]/a[contains(@href, "imdb")]/img[contains(@src, "imdb")]/../@href',
        ),
    )
    main_ids = _extract_ids(main_hrefs)
    if main_ids:
        return main_ids[0]

    # Strategy 2: any imdb link or image in the post body
    extra_hrefs = cast(
        "list[str]",
        dom.xpath(
            './/span[@class="postbody"]//a[contains(@href, "imdb")]/@href',
        ),
    )
    extra_srcs = cast(
        "list[str]",
        dom.xpath(
            './/span[@class="postbody"]//img[contains(@src, "imdb")]/@src',
        ),
    )
    extra_ids = _extract_ids(extra_hrefs + extra_srcs)

    if not extra_ids:
        return None

    # Accept only when all refs agree, or there's a single video file
    if len(set(extra_ids)) == 1 or single_file:
        return extra_ids[0]

    return None
