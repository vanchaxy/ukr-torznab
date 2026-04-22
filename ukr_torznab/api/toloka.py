from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncEngine

from ukr_torznab.api.caps import DEFAULT_LIMIT, MAX_LIMIT, caps_response
from ukr_torznab.api.search import build_rss, content_type_filter, parse_imdbid
from ukr_torznab.api.xml import error_xml
from ukr_torznab.db.queries import search_releases

router = APIRouter(prefix="/toloka")


@router.get("/api")
async def torznab_api(
    request: Request,
    t: str = "search",
    q: str | None = None,
    cat: str | None = None,
    imdbid: str | None = None,
    tvdbid: str | None = None,
    tmdbid: str | None = None,
    season: int | None = None,
    ep: int | None = None,
    offset: int = 0,
    limit: int = DEFAULT_LIMIT,
    xseed: int = 0,
) -> Response:
    if t == "caps":
        return caps_response("Toloka Torznab")

    if t not in ("search", "tvsearch", "movie"):
        return error_xml(202, "No such function")

    limit = min(max(limit, 1), MAX_LIMIT)
    offset = max(offset, 0)

    content_types = content_type_filter(
        cat,
        force_tv=(t == "tvsearch"),
        force_movie=(t == "movie"),
    )
    parsed_imdbid = parse_imdbid(imdbid)
    parsed_tvdbid = int(tvdbid) if tvdbid and tvdbid.isdigit() else None
    parsed_tmdbid = int(tmdbid) if tmdbid and tmdbid.isdigit() else None

    engine: AsyncEngine = request.app.state.engine
    async with engine.connect() as conn:
        rows = await search_releases(
            conn,
            q=q,
            content_types=content_types,
            imdb_id=parsed_imdbid,
            tvdb_id=parsed_tvdbid,
            tmdb_id=parsed_tmdbid,
            season=season,
            episode=ep,
            offset=offset,
            limit=limit,
        )

    return build_rss(rows, title="Toloka Torznab", xseed=bool(xseed))


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
