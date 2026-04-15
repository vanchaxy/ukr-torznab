import hashlib
import json
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy import and_, exists, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncConnection

from toloka_torznab.db.tables import page, release, topic
from toloka_torznab.db.upsert import upsert

PARSER_VERSION = 2


def _topic_hash(name, size, download_id, added_on, updated_at) -> str:
    h = hashlib.sha256()
    for part in (name, size, download_id, added_on, updated_at):
        h.update(str(part).encode())
    return h.hexdigest()


async def get_last_category_update(conn: AsyncConnection, *, category: str):
    query = select(
        func.max(topic.columns.updated_at),
    ).where(
        topic.columns.category == category,
    )
    result = (await conn.execute(query)).scalar()
    if result:
        return result.astimezone()
    return None


async def upsert_topic(
    conn: AsyncConnection,
    *,
    topic_data: dict,
    category: str,
):
    now = datetime.now().astimezone()
    name = topic_data["name"]
    size = topic_data["size"]
    download_id = topic_data["download_id"]
    added_on = topic_data["added_on"]
    updated_at = topic_data["updated_at"]
    id = topic_data["id"]
    computed_hash = _topic_hash(name, size, download_id, added_on, updated_at)
    values = {
        "category": category,
        "seeders": topic_data["seeders"],
        "leechers": topic_data["leechers"],
        "download_id": download_id,
        "added_on": added_on,
        "updated_at": updated_at,
        "observed_at": now,
        "name": name,
        "status": topic_data["status"],
        "size": size,
        "hash": computed_hash,
        "hash_changed_at": now,
    }
    existing = (
        await conn.execute(
            select(topic.c.hash, topic.c.hash_changed_at).where(topic.c.id == id),
        )
    ).first()
    if existing and existing.hash == computed_hash:
        values["hash_changed_at"] = existing.hash_changed_at
    stmt = upsert(topic, conn).values({"id": id, **values})
    query = stmt.on_conflict_do_update(index_elements=["id"], set_=values)
    return await conn.execute(query)


async def get_topic_id_to_download(conn: AsyncConnection):
    three_hours_ago = datetime.now().astimezone() - timedelta(hours=3)
    query = (
        select(topic.columns.id, topic.columns.download_id)
        .outerjoin(page, topic.columns.id == page.columns.id)
        .where(
            or_(
                page.columns.id == None,
                topic.columns.hash_changed_at > page.columns.downloaded_at,
                and_(
                    or_(page.columns.html == None, page.columns.torrent == None),
                    page.columns.downloaded_at <= three_hours_ago,
                ),
            ),
        )
        .limit(1)
    )
    return (await conn.execute(query)).fetchone()


async def upsert_page(
    conn: AsyncConnection,
    *,
    id,
    html,
    torrent,
    downloaded_at,
):
    values = {
        "html": html,
        "torrent": torrent,
        "downloaded_at": downloaded_at,
    }
    query = (
        upsert(page, conn)
        .values({"id": id, **values})
        .on_conflict_do_update(
            index_elements=["id"],
            set_=values,
        )
    )
    return await conn.execute(query)


async def get_page_to_parse(conn: AsyncConnection):
    query = (
        select(
            page,
            release.c.video_files_hash,
            release.c.file_to_episode,
            release.c.season_complete,
            release.c.content_hash.label("prev_content_hash"),
            release.c.hash_changed_at.label("prev_hash_changed_at"),
        )
        .outerjoin(release, page.c.id == release.c.id)
        .where(page.c.html != None)
        .where(page.c.torrent != None)
        .where(
            or_(
                release.c.id == None,
                page.c.downloaded_at > release.c.parsed_at,
                release.c.parser_version < PARSER_VERSION,
            ),
        )
        .limit(500)
    )
    return (await conn.execute(query)).fetchall()


def _file_to_episode_matches(conn, season: int | None, episode: int | None):
    dialect = conn.engine.dialect.name
    col = release.c.file_to_episode

    if dialect == "postgresql":
        fte = (
            func.json_each(func.cast(col, sa.JSON))
            .table_valued("key", "value")
            .render_derived(name="fte")
        )
        s_expr = sa.cast(fte.c.value.op("->>")(literal(0)), sa.Integer)
        e_expr = sa.cast(fte.c.value.op("->>")(literal(1)), sa.Integer)
    else:
        fte = func.json_each(col).table_valued("key", "value").render_derived(name="fte")
        s_expr = func.json_extract(fte.c.value, "$[0]")
        e_expr = func.json_extract(fte.c.value, "$[1]")

    conditions = []
    if season is not None:
        conditions.append(s_expr == season)
    if episode is not None:
        conditions.append(e_expr == episode)
    return exists(select(literal(1)).select_from(fte).where(*conditions))


async def search_releases(
    conn: AsyncConnection,
    *,
    q: str | None = None,
    content_types: list[str] | None = None,
    imdb_id: int | None = None,
    tvdb_id: int | None = None,
    tmdb_id: int | None = None,
    season: int | None = None,
    episode: int | None = None,
    offset: int = 0,
    limit: int = 100,
):
    query = (
        select(
            topic.c.id,
            topic.c.download_id,
            topic.c.name,
            topic.c.seeders,
            topic.c.leechers,
            topic.c.updated_at,
            release.c.content_type,
            release.c.imdb_id,
            release.c.tvdb_id,
            release.c.tmdb_id,
            release.c.title,
            release.c.year,
            release.c.season,
            release.c.season_complete,
            release.c.last_episode,
            release.c.torrent_size,
            release.c.infohash_sha256,
            release.c.quality,
            release.c.resolution,
            release.c.codec,
            release.c.audio_types,
            release.c.audio_sources,
            release.c.audio_lang,
            release.c.subtitle_lang,
            release.c.release_group,
            release.c.author,
        )
        .join(release, topic.c.id == release.c.id)
        .where(release.c.result == "ok")
    )
    if q:
        q_lower = q.lower()
        query = query.where(
            or_(
                func.lower(topic.c.name).like(f"%{q_lower}%"),
                func.lower(release.c.title).like(f"%{q_lower}%"),
            ),
        )
    if content_types:
        query = query.where(release.c.content_type.in_(content_types))
    if imdb_id is not None:
        query = query.where(release.c.imdb_id == imdb_id)
    if tvdb_id is not None:
        query = query.where(release.c.tvdb_id == tvdb_id)
    if tmdb_id is not None:
        query = query.where(release.c.tmdb_id == tmdb_id)
    if episode is not None:
        query = query.where(
            release.c.file_to_episode.is_not(None),
            _file_to_episode_matches(conn, season, episode),
        )
    elif season is not None:
        query = query.where(
            or_(
                and_(
                    release.c.file_to_episode.is_not(None),
                    _file_to_episode_matches(conn, season, None),
                ),
                and_(
                    release.c.file_to_episode.is_(None),
                    release.c.season == season,
                ),
            ),
        )
    query = query.order_by(topic.c.updated_at.desc()).offset(offset).limit(limit)
    return (await conn.execute(query)).fetchall()


async def upsert_release(
    conn: AsyncConnection,
    *,
    id,
    result,
    parsed_at,
    hash_changed_at,
    parsed_page=None,
):
    values = {
        "result": result,
        "parsed_at": parsed_at,
        "hash_changed_at": hash_changed_at,
    }
    if parsed_page is not None:
        p = parsed_page
        values.update(
            imdb_id=p.imdb_id,
            title=p.title,
            year=p.year,
            name=p.name,
            content_type=p.content_type.value,
            video_files=json.dumps([str(f) for f in p.video_files]),
            season=p.season,
            tvdb_id=p.tvdb_id,
            tmdb_id=p.tmdb_id,
            file_to_episode=json.dumps(
                {k: list(v) for k, v in p.file_to_episode.items()},
            )
            if p.file_to_episode
            else None,
            season_complete=p.season_complete,
            video_files_hash=p.video_files_hash,
            quality=p.quality.value,
            resolution=p.resolution.value,
            codec=p.codec.value,
            audio_types=json.dumps(sorted(v.value for v in p.audio_types)),
            audio_sources=json.dumps(sorted(v.name for v in p.audio_sources)),
            audio_lang=json.dumps(sorted(v.value for v in p.audio_lang)),
            subtitle_lang=json.dumps(sorted(v.value for v in p.subtitle_lang)),
            author=p.author,
            release_group=p.release_group,
            torrent_size=p.torrent_size,
            content_hash=p.content_hash,
            infohash_sha256=p.infohash_sha256,
            last_episode=p.last_episode,
            hdr=p.hdr.value,
            cut=p.cut,
            ratio=p.ratio.value,
            hybrid=p.hybrid,
            parser_version=PARSER_VERSION,
        )
    query = (
        upsert(release, conn)
        .values({"id": id, **values})
        .on_conflict_do_update(
            index_elements=["id"],
            set_=values,
        )
    )
    return await conn.execute(query)
