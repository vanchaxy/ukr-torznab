"""Parse-result dashboard (`/stats`): one compact row per topic, filtered and aggregated in the browser."""

import asyncio
import gzip
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncEngine

from ukr_torznab.api.info import _label, release_warnings
from ukr_torznab.db.queries import PARSER_VERSION, get_stats_rows
from ukr_torznab.models import ContentType, Release
from ukr_torznab.settings import TOLOKA_CATEGORY_NAMES

router = APIRouter(prefix="/stats")

PAGE_HTML = (Path(__file__).parent / "stats.html").read_text(encoding="utf-8")

# Building the payload touches every release row, so keep it a while.
DATA_TTL = 5 * 60
_data_cache: tuple[float, bytes, bytes] | None = None  # (built at, json, gzipped json)
_data_lock = asyncio.Lock()

# (key, label, multi-valued). The page renders the facets in this order.
DIMS: list[tuple[str, str, bool]] = [
    ("year", "Posting year", False),
    ("category", "Category", False),
    ("state", "Parse result", False),
    ("content_type", "Content type", False),
    ("quality", "Quality", False),
    ("resolution", "Resolution", False),
    ("codec", "Video codec", False),
    ("hdr", "HDR", False),
    ("ratio", "Aspect ratio", False),
    ("hybrid", "Hybrid", False),
    ("audio_types", "Audio type", True),
    ("audio_sources", "Audio source", True),
    ("audio_lang", "Audio language", True),
    ("subtitle_lang", "Subtitle language", True),
    ("warnings", "Warnings", True),
    ("episodes", "TV episode mapping", False),
    ("decade", "Release decade (IMDb)", False),
    ("release_group", "Release group", False),
    ("author", "Author", False),
    ("parser", "Parser version", False),
]


def _category_name(category: str) -> str:
    cat_id = category.removeprefix("f")
    return TOLOKA_CATEGORY_NAMES.get(cat_id, category)


def _removed(row) -> bool:
    # Gone from toloka's listings with no HTML to (re)parse, so nothing will ever process it.
    return not row.observed and not row.has_html


def _state(row) -> str:
    if _removed(row):
        return "removed"
    if row.release_id is None:
        return "pending" if row.downloaded else "not downloaded"
    return "ok" if row.result == "ok" else row.result


def _episodes(rel: Release) -> str | None:
    if rel.content_type is not ContentType.TV:
        return None
    if not rel.file_to_episode:
        return "no episode map"
    return "complete season" if rel.season_complete else "partial season"


def _row_values(row) -> dict[str, Any]:
    values: dict[str, Any] = {
        "year": str(row.added_on.year),
        "category": _category_name(row.category),
        "state": _state(row),
        "parser": None
        if row.parser_version is None
        else f"v{row.parser_version}"
        + ("" if row.parser_version >= PARSER_VERSION or _removed(row) else " (stale)"),
    }
    if row.result != "ok":
        return values

    rel = Release.from_db_row(row)
    values.update(
        content_type=rel.content_type.value,
        quality=_label(rel.quality),
        resolution=rel.resolution.value,
        codec=_label(rel.codec),
        hdr=rel.hdr.value,
        ratio=_label(rel.ratio),
        hybrid="hybrid" if rel.hybrid else "no",
        audio_types=[_label(t) for t in rel.audio_types] or ["none"],
        audio_sources=[_label(s) for s in rel.audio_sources] or ["none"],
        audio_lang=[_label(lang) for lang in rel.audio_lang] or ["none"],
        subtitle_lang=[_label(lang) for lang in rel.subtitle_lang] or ["none"],
        warnings=release_warnings(rel) or ["none"],
        episodes=_episodes(rel),
        decade=f"{rel.year // 10 * 10}s" if rel.year else "unknown",
        release_group=rel.release_group or "none",
        author=rel.author or "none",
    )
    return values


def build_stats(rows) -> dict[str, Any]:
    """Dictionary-encode every dimension: each row holds indexes into `dims[key]["values"]`.

    Scalar columns hold an index or null (not applicable, e.g. quality of a skipped topic);
    multi-valued columns hold a list of indexes.
    """
    lookups: dict[str, dict[str, int]] = {key: {} for key, _, _ in DIMS}
    columns: dict[str, list[Any]] = {key: [] for key, _, _ in DIMS}
    ids: list[int] = []
    names: list[str] = []

    def encode(key: str, value: str) -> int:
        lookup = lookups[key]
        if value not in lookup:
            lookup[value] = len(lookup)
        return lookup[value]

    for row in rows:
        ids.append(row.id)
        names.append(row.name)
        values = _row_values(row)
        for key, _, multi in DIMS:
            value = values.get(key)
            if value is None:
                columns[key].append(None)
            elif multi:
                columns[key].append(sorted(encode(key, v) for v in value))
            else:
                columns[key].append(encode(key, value))

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "parser_version": PARSER_VERSION,
        "count": len(ids),
        "dims": [
            {"key": key, "label": label, "multi": multi, "values": list(lookups[key])}
            for key, label, multi in DIMS
        ],
        "ids": ids,
        "names": names,
        "columns": columns,
    }


async def _get_data(engine: AsyncEngine) -> tuple[bytes, bytes]:
    global _data_cache
    async with _data_lock:
        if _data_cache is None or time.monotonic() - _data_cache[0] >= DATA_TTL:
            async with engine.connect() as conn:
                rows = await get_stats_rows(conn)

            def encode() -> tuple[bytes, bytes]:
                body = json.dumps(build_stats(rows), ensure_ascii=False, separators=(",", ":"))
                raw = body.encode()
                return raw, gzip.compress(raw, compresslevel=6)

            raw, gz = await asyncio.to_thread(encode)
            _data_cache = (time.monotonic(), raw, gz)
        return _data_cache[1], _data_cache[2]


@router.get("", response_class=HTMLResponse)
async def stats_page() -> HTMLResponse:
    return HTMLResponse(PAGE_HTML)


@router.get("/data")
async def stats_data(request: Request) -> Response:
    raw, gz = await _get_data(request.app.state.engine)
    if "gzip" in request.headers.get("accept-encoding", ""):
        return Response(
            gz,
            media_type="application/json",
            headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"},
        )
    return Response(raw, media_type="application/json", headers={"Vary": "Accept-Encoding"})
