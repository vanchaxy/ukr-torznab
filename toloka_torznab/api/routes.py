"""Torznab API route handlers."""

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncEngine

from toloka_torznab.db.queries import search_releases

from .caps import caps_response
from .search import build_rss, content_type_filter, parse_imdbid
from .xml import _CT_TORRENT, _DEFAULT_LIMIT, _MAX_LIMIT, error_xml

router = APIRouter()
app = FastAPI()


@router.get("/api")
async def torznab_api(
    request: Request,
    t: str = "search",
    q: str | None = None,
    cat: str | None = None,
    imdbid: str | None = None,
    tvdbid: str | None = None,
    season: int | None = None,
    ep: int | None = None,
    offset: int = 0,
    limit: int = _DEFAULT_LIMIT,
) -> Response:
    if t == "caps":
        return caps_response()

    if t not in ("search", "tvsearch", "movie"):
        return error_xml(202, "No such function")

    limit = min(max(limit, 1), _MAX_LIMIT)
    offset = max(offset, 0)

    content_types = content_type_filter(
        cat,
        force_tv=(t == "tvsearch"),
        force_movie=(t == "movie"),
    )
    parsed_imdbid = parse_imdbid(imdbid)
    parsed_tvdbid = int(tvdbid) if tvdbid and tvdbid.isdigit() else None

    engine: AsyncEngine = request.app.state.engine
    async with engine.connect() as conn:
        rows = await search_releases(
            conn,
            q=q,
            content_types=content_types,
            imdb_id=parsed_imdbid,
            tvdb_id=parsed_tvdbid,
            season=season,
            episode=ep,
            offset=offset,
            limit=limit,
        )

    base_url = str(request.base_url).rstrip("/")
    return build_rss(rows, base_url)


@router.get("/download/{download_id}")
async def download_torrent(request: Request, download_id: int) -> Response:
    torrent_data = await request.app.state.toloka_client.download_torrent(download_id)
    if not torrent_data:
        raise HTTPException(status_code=502, detail="Failed to fetch torrent from Toloka")

    return Response(
        content=torrent_data,
        media_type=_CT_TORRENT,
        headers={"Content-Disposition": f'attachment; filename="{download_id}.torrent"'},
    )


app.include_router(router)
