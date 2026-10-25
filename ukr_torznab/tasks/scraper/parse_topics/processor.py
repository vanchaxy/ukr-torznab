import hashlib
import html as html_mod
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import html2text
import libtorrent as lt
from lxml import etree
from lxml.etree import _Element, tostring
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from ukr_torznab.clients.servarr import ServarrClient
from ukr_torznab.clients.skyhook import SkyhookClient
from ukr_torznab.db.tables import imdb_titles as imdb_titles_table
from ukr_torznab.models import AudioType, ContentType
from ukr_torznab.tasks.scraper.parse_topics.episodes import match_episodes, match_episodes_llm
from ukr_torznab.tasks.scraper.parse_topics.extras import (
    detect_cut,
    detect_hdr,
    detect_hybrid,
    detect_ratio,
)
from ukr_torznab.tasks.scraper.parse_topics.hash import content_hash, hash_video_files
from ukr_torznab.tasks.scraper.parse_topics.imdb import extract_imdb
from ukr_torznab.tasks.scraper.parse_topics.metadata import (
    detect_audio_sources,
    detect_audio_types,
    detect_author,
    detect_codec,
    detect_languages,
    detect_quality,
    detect_release_group,
    detect_resolution,
    resolve_original_lang,
)
from ukr_torznab.tasks.scraper.parse_topics.models import ParsedPage, SkippedPage, SkipReason
from ukr_torznab.tasks.scraper.parse_topics.season import detect_season
from ukr_torznab.utils import ALLOWED_EXTENSIONS, EPOCH, VIDEO_EXTENSIONS, toloka_display_tz

logger = logging.getLogger(__name__)


H2T = html2text.HTML2Text(bodywidth=0)


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
        registered_at = (
            datetime.strptime(raw_reg, "%Y-%m-%d %H:%M")
            .replace(tzinfo=toloka_display_tz(page.downloaded_at))
            .astimezone(UTC)
        )
    else:
        registered_at = EPOCH

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
    except Exception:  # noqa: BLE001 - libtorrent raises bare RuntimeError on bad bencode
        return SkippedPage(pid, SkipReason.INVALID_TORRENT)

    ti = lt.torrent_info(cast("lt.TorrentFileDict", metadata))
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
    imdb_raw = extract_imdb(dom, single_file=single_file)
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

    dom_str = tostring(dom).decode("utf-8")
    html_lower = html_mod.unescape(dom_str).lower()
    text = "\n".join(filter(str.strip, H2T.handle(html_lower).splitlines()))

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

    # Episode matching
    file_to_episode = None
    season_complete = None
    video_files_hash = None
    if content_type is ContentType.TV and skyhook and season is not None:
        current_hash = hash_video_files(video_files)
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

    # Author and release group
    author = detect_author(dom)
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
        original_lang = resolve_original_lang(original_code)
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
    page.content_hash = content_hash(page)
    return page
