"""Main processing pipeline.

Reads every page from the database and yields either a fully-populated
:class:`ParsedPage` or a :class:`SkippedPage` with the reason it was
excluded.
"""

from __future__ import annotations

import dataclasses
import hashlib
import html as html_mod
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

import html2text
import libtorrent as lt  # type: ignore[import-untyped]
from lxml import etree
from lxml.etree import _Element, tostring
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from ukr_torznab.clients.servarr import ServarrClient
from ukr_torznab.clients.skyhook import SkyhookClient
from ukr_torznab.db.tables import imdb_titles as imdb_titles_table
from ukr_torznab.enums import AudioType, ContentType, Lang, SkipReason
from ukr_torznab.tasks.scraper.parse_topics.episodes import match_episodes, match_episodes_llm
from ukr_torznab.tasks.scraper.parse_topics.extras import (
    detect_cut,
    detect_hdr,
    detect_hybrid,
    detect_ratio,
)
from ukr_torznab.tasks.scraper.parse_topics.imdb import extract_imdb_multi
from ukr_torznab.tasks.scraper.parse_topics.metadata import (
    detect_audio_sources,
    detect_audio_types,
    detect_codec,
    detect_languages,
    detect_quality,
    detect_release_group,
    detect_resolution,
)
from ukr_torznab.tasks.scraper.parse_topics.models import ParsedPage, SkippedPage
from ukr_torznab.tasks.scraper.parse_topics.season import detect_season
from ukr_torznab.tasks.scraper.parse_topics.utils import ALLOWED_EXTENSIONS, VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)
_h2t = html2text.HTML2Text(bodywidth=0)

_AUTHOR_DISALLOWED = re.compile(r"[^a-zа-яёіїєґ0-9_-]+")

# ISO 639-2/T (3-letter, used by Skyhook) → ISO 639-1 (2-letter, used by Lang)
_ISO3_TO_LANG: dict[str, Lang] = {
    "ukr": Lang.UKRAINIAN,
    "eng": Lang.ENGLISH,
    "spa": Lang.SPANISH,
    "fra": Lang.FRENCH,
    "fre": Lang.FRENCH,
    "zho": Lang.CHINESE,
    "chi": Lang.CHINESE,
    "tha": Lang.THAI,
    "jpn": Lang.JAPANESE,
    "kor": Lang.KOREAN,
    "deu": Lang.GERMAN,
    "ger": Lang.GERMAN,
    "nor": Lang.NORWEGIAN,
    "ita": Lang.ITALIAN,
    "fin": Lang.FINNISH,
    "srp": Lang.SERBIAN,
    "nld": Lang.DUTCH,
    "dut": Lang.DUTCH,
    "swe": Lang.SWEDISH,
    "ron": Lang.ROMANIAN,
    "rum": Lang.ROMANIAN,
    "rus": Lang.RUSSIAN,
    "ara": Lang.ARABIC,
    "dan": Lang.DANISH,
    "hrv": Lang.CROATIAN,
    "pol": Lang.POLISH,
    "por": Lang.PORTUGUESE,
    "ces": Lang.CZECH,
    "cze": Lang.CZECH,
    "hin": Lang.HINDI,
    "est": Lang.ESTONIAN,
    "bul": Lang.BULGARIAN,
    "ell": Lang.GREEK,
    "gre": Lang.GREEK,
    "hun": Lang.HUNGARIAN,
    "mol": Lang.MOLDOVAN,
    "slv": Lang.SLOVENIAN,
    "tur": Lang.TURKISH,
    "fas": Lang.PERSIAN,
    "per": Lang.PERSIAN,
    "isl": Lang.ICELANDIC,
    "ice": Lang.ICELANDIC,
    "slk": Lang.SLOVAK,
    "slo": Lang.SLOVAK,
    "ind": Lang.INDONESIAN,
    "afr": Lang.AFRIKAANS,
}


def _resolve_original_lang(code: str | None) -> Lang | None:
    if not code:
        return None
    code = code.lower()
    if len(code) == 3:
        return _ISO3_TO_LANG.get(code)
    try:
        return Lang(code)
    except ValueError:
        return None


def _hash_video_files(files: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(str(f) for f in files):
        h.update(p.encode())
    return h.hexdigest()


def _normalise(val: object) -> str:
    if isinstance(val, (set, frozenset)):
        return repr(sorted(_normalise(v) for v in val))
    if isinstance(val, list):
        return repr(sorted(_normalise(v) for v in val))
    if isinstance(val, dict):
        return repr(sorted((_normalise(k), _normalise(v)) for k, v in val.items()))
    return repr(val)


def _content_hash(page: ParsedPage) -> str:
    h = hashlib.sha256()
    for f in dataclasses.fields(page):
        if f.name == "content_hash":
            continue
        h.update(_normalise(getattr(page, f.name)).encode())
    return h.hexdigest()


async def process_single_page(
    conn: AsyncConnection,
    skyhook_client: SkyhookClient,
    servarr_client: ServarrClient,
    page,
    *,
    cached_video_files_hash: str | None = None,
    cached_file_to_episode: dict[str, tuple[int, int]] | None = None,
    cached_season_complete: bool | None = None,
    openai_client: AsyncOpenAI | None = None,
) -> ParsedPage | SkippedPage:
    pid = page.id

    # 1. Parse HTML structure
    dom_full = etree.HTML(page.html)

    raw_reg = (
        cast(
            "str",
            dom_full.xpath(
                "normalize-space(//tr[@class='row4_to' and td[contains(., 'Зареєстрований:')]]/td[2])",
            ),
        )
        .replace("\xa0", "")
        .strip()
    )
    if raw_reg:
        kyiv_dt = datetime.strptime(raw_reg, "%Y-%m-%d %H:%M").replace(
            tzinfo=ZoneInfo("Europe/Kyiv"),
        )
        registered_at = kyiv_dt.astimezone(UTC)
    else:
        registered_at = datetime(1970, 1, 1, tzinfo=UTC)

    dom_list = cast(
        "list[_Element]",
        dom_full.xpath(
            '//table[@class="forumline"]/tr[.//div[@class="files-wrap"]]',
        ),
    )
    if len(dom_list) != 1:
        return SkippedPage(pid, SkipReason.UNEXPECTED_PAGE_STRUCTURE)
    dom: _Element = dom_list[0]

    # 2. Parse torrent metadata
    try:
        metadata = lt.bdecode(page.torrent)
    except Exception:
        return SkippedPage(pid, SkipReason.INVALID_TORRENT)

    ti = lt.torrent_info(metadata)
    torrent_size = ti.total_size()
    infohash_sha256 = hashlib.sha256(bytes.fromhex(str(ti.info_hash()))).hexdigest()
    ti_files = ti.files()
    files = [Path(ti_files.file_path(i).lower()) for i in range(ti_files.num_files())]

    # 3. Extension filter
    if any(f.suffix not in ALLOWED_EXTENSIONS for f in files):
        return SkippedPage(pid, SkipReason.DISALLOWED_FILE_EXTENSION)

    video_files = [f for f in files if f.suffix in VIDEO_EXTENSIONS]
    if not video_files:
        return SkippedPage(pid, SkipReason.NO_VIDEO_FILES)

    # 4. IMDB extraction
    single_file = len(video_files) == 1
    imdb_raw = extract_imdb_multi(dom, single_file=single_file)
    if imdb_raw is None:
        return SkippedPage(pid, SkipReason.NO_IMDB_LINK)
    imdb: int = int(imdb_raw[2:])

    # 5. Title type lookup
    row = (
        await conn.execute(
            select(
                imdb_titles_table.c.title_type,
                imdb_titles_table.c.primary_title,
                imdb_titles_table.c.original_title,
                imdb_titles_table.c.start_year,
            ).where(imdb_titles_table.c.id == imdb),
        )
    ).first()
    if not row:
        return SkippedPage(pid, SkipReason.IMDB_NOT_IN_DATABASE)
    title_type, primary_title, original_title, start_year = row
    imdb_title: str = primary_title or original_title

    # 6. Content type & external metadata
    skyhook: dict | None = None
    servarr: dict | None = None
    if title_type in ("tvSeries", "tvMiniSeries"):
        content_type = ContentType.TV
        skyhook = await skyhook_client.get_metadata(conn, imdb)
        if not skyhook:
            return SkippedPage(pid, SkipReason.TV_NO_SKYHOOK_METADATA)
    else:
        content_type = ContentType.MOVIE
        servarr = await servarr_client.get_metadata(conn, imdb)
        if not servarr:
            return SkippedPage(pid, SkipReason.MOVIE_NO_SERVARR_METADATA)

    # 7. Movie: must have single video file
    if content_type is ContentType.MOVIE and len(video_files) > 1:
        return SkippedPage(pid, SkipReason.MOVIE_MULTIPLE_VIDEO_FILES)

    # 8. Folder structure check
    parents = {f.parent for f in video_files}
    if len(parents) != 1 and len(parents) != len(video_files):
        return SkippedPage(pid, SkipReason.INCONSISTENT_FOLDER_STRUCTURE)

    # 9. Season detection (TV only)
    name = str(cast("list", dom.xpath('//a[@class="maintitle"]/text()'))[0]).lower()
    season: int | None = None
    if content_type is ContentType.TV:
        season = detect_season(name, video_files)
        if season is None:
            return SkippedPage(pid, SkipReason.CANNOT_DETERMINE_SEASON)

    # Prefer external metadata title/year over IMDB
    effective_title = imdb_title
    effective_year = start_year
    if content_type is ContentType.TV and skyhook:
        effective_title = skyhook.get("title") or imdb_title
        first_aired = skyhook.get("firstAired")
        if first_aired:
            effective_year = int(first_aired[:4])
    elif content_type is ContentType.MOVIE and servarr:
        effective_title = servarr.get("Title") or imdb_title
        effective_year = servarr.get("Year") or start_year

    # --- Passed all filters – build the full record -------------------------
    dom_str = tostring(dom).decode("utf-8")
    html_lower = html_mod.unescape(dom_str).lower()
    text = "\n".join(filter(str.strip, _h2t.handle(html_lower).splitlines()))

    # Episode matching
    file_to_episode = None
    season_complete = None
    video_files_hash = None
    if content_type is ContentType.TV and skyhook and season is not None:
        current_hash = _hash_video_files(video_files)
        if cached_video_files_hash == current_hash:
            file_to_episode = cached_file_to_episode
            season_complete = cached_season_complete
            video_files_hash = current_hash
        else:
            ep_result = match_episodes(video_files, skyhook, int(season))
            if ep_result is not None:
                file_to_episode, season_complete = ep_result
                video_files_hash = current_hash
            elif openai_client is not None:
                llm_result = await match_episodes_llm(
                    video_files,
                    skyhook,
                    int(season),
                    openai_client,
                )
                if llm_result is not None:
                    file_to_episode, season_complete, season = llm_result
                    video_files_hash = current_hash

    # Last episode
    last_episode: int | None = None
    if file_to_episode and season is not None:
        episodes = [ep for s, ep in file_to_episode.values() if s == season]
        if episodes:
            last_episode = max(episodes)

    # Author
    author_raw = str(cast("list", dom.xpath('//span[@class="name"]//text()'))[0]).lower()
    author: str | None = _AUTHOR_DISALLOWED.sub("", author_raw) or None

    # Release group
    release_group = detect_release_group(ti.name().lower())

    # Media metadata
    audio_types = detect_audio_types(text)
    audio_lang, sub_lang = detect_languages(text)
    if AudioType.ORIGINAL in audio_types:
        original_code = (
            skyhook.get("originalLanguage")
            if skyhook
            else servarr.get("OriginalLanguage")
            if servarr
            else None
        )
        original_lang = _resolve_original_lang(original_code)
        if original_lang is not None:
            audio_lang = audio_lang | {original_lang}

    page = ParsedPage(
        page_id=pid,
        imdb_id=imdb,
        title=effective_title,
        year=effective_year,
        name=name,
        content_type=content_type,
        video_files=video_files,
        registered_at=registered_at,
        season=int(season) if season is not None else None,
        tvdb_id=skyhook.get("tvdbId") if skyhook else None,
        tmdb_id=servarr.get("TmdbId") if servarr else None,
        file_to_episode=file_to_episode,
        season_complete=season_complete,
        video_files_hash=video_files_hash,
        last_episode=last_episode,
        quality=detect_quality(text, name),
        resolution=detect_resolution(text, name),
        codec=detect_codec(text, html_lower),
        audio_types=audio_types,
        audio_sources=detect_audio_sources(html_lower, text),
        audio_lang=audio_lang,
        subtitle_lang=sub_lang,
        author=author,
        release_group=release_group,
        torrent_size=torrent_size,
        infohash_sha256=infohash_sha256,
        hdr=detect_hdr(text),
        cut=detect_cut(name),
        ratio=detect_ratio(name),
        hybrid=detect_hybrid(name),
    )
    page.content_hash = _content_hash(page)
    return page
