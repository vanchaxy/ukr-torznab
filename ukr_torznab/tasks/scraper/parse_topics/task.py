import asyncio
import json
import logging
from datetime import datetime

from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from ukr_torznab.clients.servarr import ServarrClient
from ukr_torznab.clients.skyhook import SkyhookClient
from ukr_torznab.db.queries import get_page_to_parse, upsert_release
from ukr_torznab.db.tables import imdb_titles
from ukr_torznab.tasks.base import AbstractTask
from ukr_torznab.tasks.scraper.parse_topics.models import SkippedPage
from ukr_torznab.tasks.scraper.parse_topics.processor import process_single_page

logger = logging.getLogger(__name__)


class ParseTopicsTask(AbstractTask):
    def __init__(
        self,
        engine: AsyncEngine,
        skyhook_client: SkyhookClient,
        servarr_client: ServarrClient,
        openai_client: AsyncOpenAI | None = None,
    ):
        self.engine = engine
        self.skyhook_client = skyhook_client
        self.servarr_client = servarr_client
        self.openai_client = openai_client
        self._imdb_ready = False

    async def run_once(self):
        if not self._imdb_ready:
            async with self.engine.connect() as conn:
                imdb_count = (
                    await conn.execute(select(func.count()).select_from(imdb_titles))
                ).scalar()
            if not imdb_count:
                logger.warning(
                    "imdb_titles table is empty, skipping parse — waiting for RefreshImdbTask",
                )
                for _ in range(60):
                    if not self.running:
                        return
                    await asyncio.sleep(1)
                return
            logger.info("imdb_titles table is ready (%d rows)", imdb_count)
            self._imdb_ready = True

        async with self.engine.begin() as conn:
            rows = await get_page_to_parse(conn)
            if not rows:
                logger.info("No pages to parse, sleeping")
                for _ in range(60):
                    if not self.running:
                        return
                    await asyncio.sleep(1)
                return

            logger.info("Parsing %d pages", len(rows))
            for row in rows:
                if not self.running:
                    return
                cached_hash = row.video_files_hash
                cached_fte = None
                if row.file_to_episode:
                    cached_fte = {k: tuple(v) for k, v in json.loads(row.file_to_episode).items()}
                cached_sc = row.season_complete

                logger.info("Parsing page %s", row.id)
                result = await process_single_page(
                    conn,
                    self.skyhook_client,
                    self.servarr_client,
                    row,
                    cached_video_files_hash=cached_hash,
                    cached_file_to_episode=cached_fte,
                    cached_season_complete=cached_sc,
                    openai_client=self.openai_client,
                )

                now = datetime.now().astimezone()

                if isinstance(result, SkippedPage):
                    logger.info("Page %s skipped: %s", row.id, result.reason.name)
                    await upsert_release(
                        conn,
                        id=row.id,
                        result=result.reason.name,
                        parsed_at=now,
                        hash_changed_at=now,
                    )
                else:
                    prev_hash = row.prev_content_hash
                    if result.content_hash != prev_hash:
                        hash_changed_at = now
                        logger.info("Page %s: content hash changed", row.id)
                    else:
                        hash_changed_at = row.prev_hash_changed_at or now

                    if result.season is not None:
                        logger.info(
                            "Page %s parsed ok: %s S%02d",
                            row.id,
                            result.title,
                            result.season,
                        )
                    else:
                        logger.info("Page %s parsed ok: %s (%s)", row.id, result.title, result.year)

                    await upsert_release(
                        conn,
                        id=row.id,
                        result="ok",
                        parsed_at=now,
                        hash_changed_at=hash_changed_at,
                        parsed_page=result,
                    )
