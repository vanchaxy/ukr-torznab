from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncEngine

from ukr_torznab.api.caps import caps_response
from ukr_torznab.api.search import SEARCH_FUNCTIONS, SearchParams, build_rss, search_params
from ukr_torznab.api.xml import error_xml
from ukr_torznab.db.queries import search_releases

router = APIRouter(prefix="/toloka")

TITLE = "Toloka Torznab"


@router.get("/api")
async def torznab_api(
    request: Request,
    params: Annotated[SearchParams, Depends(search_params)],
) -> Response:
    if params.t == "caps":
        return caps_response(TITLE)

    if params.t not in SEARCH_FUNCTIONS:
        return error_xml(202, "No such function")

    engine: AsyncEngine = request.app.state.engine
    async with engine.connect() as conn:
        rows = await search_releases(
            conn,
            q=params.q,
            content_types=params.content_types,
            imdb_id=params.imdb_id,
            tvdb_id=params.tvdb_id,
            tmdb_id=params.tmdb_id,
            season=params.season,
            episode=params.episode,
            offset=params.offset,
            limit=params.limit,
        )

    return build_rss(rows, title=TITLE, xseed=params.xseed)


@router.get("/download/{download_id}")
async def download_torrent(request: Request, download_id: int) -> Response:
    torrent_data = await request.app.state.toloka_client.download_torrent(download_id)
    if not torrent_data:
        raise HTTPException(status_code=502, detail="Failed to fetch torrent from Toloka")

    return Response(
        content=torrent_data,
        media_type="application/x-bittorrent",
        headers={"Content-Disposition": f'attachment; filename="{download_id}.torrent"'},
    )
