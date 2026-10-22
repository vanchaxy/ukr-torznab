from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from ukr_torznab.api.caps import caps_response
from ukr_torznab.api.search import SEARCH_FUNCTIONS, SearchParams, build_rss, search_params
from ukr_torznab.api.xml import error_xml
from ukr_torznab.clients.utp import UtpClient

router = APIRouter(prefix="/utp")

TITLE = "UTP Torznab"

UTP_CAT_MOVIE = 1
UTP_CAT_TV = 2


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
