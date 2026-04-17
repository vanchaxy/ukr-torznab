"""UTP Torznab API route handlers — proxies requests to utp.to unit3D API."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ukr_torznab.api.caps import DEFAULT_LIMIT, MAX_LIMIT, caps_response
from ukr_torznab.api.search import build_rss, content_type_filter, parse_imdbid
from ukr_torznab.api.xml import error_xml
from ukr_torznab.clients.utp import UtpClient, transform_utp_item

router = APIRouter(prefix="/utp")

# unit3D category IDs: 1 = Movies, 2 = TV
_UTP_CAT_MOVIE = 1
_UTP_CAT_TV = 2


@router.get("/api")
async def utp_torznab_api(
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
) -> Response:
    if t == "caps":
        return caps_response("UTP Torznab")

    if t not in ("search", "tvsearch", "movie"):
        return error_xml(202, "No such function")

    utp_client: UtpClient | None = getattr(request.app.state, "utp_client", None)
    if utp_client is None:
        return error_xml(900, "UTP client not configured (set UTP_API_KEY)")

    limit = min(max(limit, 1), MAX_LIMIT)
    offset = max(offset, 0)

    content_types = content_type_filter(
        cat,
        force_tv=(t == "tvsearch"),
        force_movie=(t == "movie"),
    )

    # Map content_types to unit3D category IDs
    categories: list[int] | None = None
    if content_types:
        categories = []
        if "tv" in content_types:
            categories.append(_UTP_CAT_TV)
        if "movie" in content_types:
            categories.append(_UTP_CAT_MOVIE)

    parsed_imdbid = parse_imdbid(imdbid)
    parsed_tvdbid = int(tvdbid) if tvdbid and tvdbid.isdigit() else None
    parsed_tmdbid = int(tmdbid) if tmdbid and tmdbid.isdigit() else None

    page = (offset // limit) + 1

    raw_items = await utp_client.search(
        name=q,
        imdb_id=parsed_imdbid,
        tvdb_id=parsed_tvdbid,
        tmdb_id=parsed_tmdbid,
        categories=categories,
        season=season,
        episode=ep,
        per_page=limit,
        page=page,
    )

    items = [transform_utp_item(it) for it in raw_items]

    base_url = str(request.base_url).rstrip("/")
    return build_rss(items, base_url, source="utp")
