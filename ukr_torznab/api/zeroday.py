import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncEngine

from ukr_torznab.api.caps import caps_response
from ukr_torznab.api.search import SEARCH_FUNCTIONS, SearchParams, build_rss, search_params
from ukr_torznab.api.xml import error_xml
from ukr_torznab.clients.zeroday.client import ZerodayClient
from ukr_torznab.clients.zeroday.parser import MOVIE_CATEGORIES, TV_CATEGORIES
from ukr_torznab.models import Lang, Release

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/0day")

TITLE = "0day Torznab"


async def _title_for_ids(request: Request, params: SearchParams, *, tv: bool) -> str | None:
    """0day only searches by text, so an id search looks the title up first."""
    if params.imdb_id is None:
        return None
    engine: AsyncEngine = request.app.state.engine
    client = request.app.state.skyhook_client if tv else request.app.state.servarr_client
    async with engine.begin() as conn:
        meta = await client.get_metadata(conn, params.imdb_id)
    if not meta:
        return None
    return meta.get("title") if tv else meta.get("Title")


def _matches(release: Release, params: SearchParams) -> bool:
    # 0day also carries Russian-only and English-only releases; other indexers cover those.
    if Lang.UKRAINIAN not in release.audio_lang:
        return False
    if params.imdb_id is not None and release.imdb_id != params.imdb_id:
        return False
    if params.season is not None and (not release.is_tv or release.season != params.season):
        return False
    if params.episode is not None and release.min_episode is not None:
        return release.min_episode <= params.episode <= (release.max_episode or 0)
    return True


@router.get("/api")
async def zeroday_torznab_api(
    request: Request,
    params: Annotated[SearchParams, Depends(search_params)],
) -> Response:
    if params.t == "caps":
        return caps_response(TITLE)

    if params.t not in SEARCH_FUNCTIONS:
        return error_xml(202, "No such function")

    client: ZerodayClient | None = request.app.state.zeroday_client
    if client is None:
        return error_xml(900, "0day client not configured (set ZERODAY_USERNAME)")

    types = params.content_types or ["movie", "tv"]
    categories = (MOVIE_CATEGORIES if "movie" in types else set()) | (
        TV_CATEGORIES if "tv" in types else set()
    )

    query = params.q
    if not query and params.imdb_id is not None:
        query = await _title_for_ids(request, params, tv=types == ["tv"])
        if not query:
            return build_rss([], title=TITLE)

    rows = await client.browse(query, categories)
    releases = await client.releases(request.app.state.engine, rows)
    items = [r for r in releases if _matches(r, params)]
    return build_rss(items[params.offset : params.offset + params.limit], title=TITLE)


@router.get("/download/{topic_id}")
async def download_torrent(request: Request, topic_id: int) -> Response:
    client: ZerodayClient | None = request.app.state.zeroday_client
    if client is None:
        raise HTTPException(status_code=404, detail="0day client not configured")
    try:
        torrent_data = await client.download_torrent(topic_id)
    except httpx.HTTPError as e:
        logger.warning("0day torrent %s: download failed: %r", topic_id, e)
        torrent_data = None
    if not torrent_data:
        raise HTTPException(status_code=502, detail="Failed to fetch torrent from 0day")

    return Response(
        content=torrent_data,
        media_type="application/x-bittorrent",
        headers={"Content-Disposition": f'attachment; filename="{topic_id}.torrent"'},
    )
