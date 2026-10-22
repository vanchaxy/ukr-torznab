import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from ukr_torznab.api.caps import caps_response
from ukr_torznab.api.info import utp_item_info
from ukr_torznab.api.search import SEARCH_FUNCTIONS, SearchParams, build_rss, search_params
from ukr_torznab.api.xml import error_xml
from ukr_torznab.clients.utp import UtpClient

router = APIRouter(prefix="/utp")

TITLE = "UTP Torznab"

UTP_CAT_MOVIE = 1
UTP_CAT_TV = 2

# The UTP client is limited to 1 req/s and list pages ask for every row, so keep answers a while.
INFO_TTL = 15 * 60
INFO_CACHE_MAX = 5000
_info_cache: dict[int, tuple[float, dict[str, Any]]] = {}


@router.get("/api")
async def utp_torznab_api(
    request: Request,
    params: Annotated[SearchParams, Depends(search_params)],
) -> Response:
    if params.t == "caps":
        return caps_response(TITLE)

    if params.t not in SEARCH_FUNCTIONS:
        return error_xml(202, "No such function")

    utp_client: UtpClient | None = request.app.state.utp_client
    if utp_client is None:
        return error_xml(900, "UTP client not configured (set UTP_API_KEY)")

    categories: list[int] | None = None
    if params.content_types:
        categories = []
        if "tv" in params.content_types:
            categories.append(UTP_CAT_TV)
        if "movie" in params.content_types:
            categories.append(UTP_CAT_MOVIE)

    items = await utp_client.search(
        name=params.q,
        imdb_id=params.imdb_id,
        tvdb_id=params.tvdb_id,
        tmdb_id=params.tmdb_id,
        categories=categories,
        season=params.season,
        episode=params.episode,
        per_page=params.limit,
        page=(params.offset // params.limit) + 1,
    )

    return build_rss(items, title=TITLE, xseed=params.xseed)


@router.get("/info/{torrent_id}")
async def utp_info(request: Request, torrent_id: int) -> dict[str, Any]:
    """Parsed view of one UTP torrent, for the browser extension."""
    utp_client: UtpClient | None = request.app.state.utp_client
    if utp_client is None:
        raise HTTPException(status_code=503, detail="UTP client not configured (set UTP_API_KEY)")

    now = time.monotonic()
    cached = _info_cache.get(torrent_id)
    if cached is not None and now - cached[0] < INFO_TTL:
        return cached[1]

    item = await utp_client.get_item(str(torrent_id))
    if item is None:
        raise HTTPException(status_code=502, detail="Failed to fetch torrent from UTP")
    info = utp_item_info(item)

    if len(_info_cache) >= INFO_CACHE_MAX:
        for key in [k for k, (t, _) in _info_cache.items() if now - t >= INFO_TTL]:
            del _info_cache[key]
        if len(_info_cache) >= INFO_CACHE_MAX:
            _info_cache.clear()
    _info_cache[torrent_id] = (now, info)
    return info
