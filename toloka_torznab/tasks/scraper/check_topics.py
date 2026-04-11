import asyncio
import logging

import sqlalchemy as sa

from toloka_torznab.db.queries import upsert_topic
from toloka_torznab.db.tables import topic as topic_table
from toloka_torznab.settings import TOLOKA_CATEGORIES
from toloka_torznab.tasks.base import AbstractTask

logger = logging.getLogger(__name__)


class RefreshTopicsTask(AbstractTask):
    def __init__(self, client, engine):
        self.client = client
        self.engine = engine

    async def run_once(self):
        async with self.engine.connect() as conn:
            topic_count = (
                await conn.execute(sa.select(sa.func.count()).select_from(topic_table))
            ).scalar()
        if topic_count and topic_count >= 30_000:
            logger.info("RefreshTopicsTask: waiting before full category refresh")
            for _ in range(10 * 60 * 60):
                if not self.running:
                    return
                await asyncio.sleep(1)
        else:
            logger.info(
                "RefreshTopicsTask: only %d topics in DB, refreshing immediately",
                topic_count or 0,
            )

        logger.info(
            "RefreshTopicsTask: starting full refresh of %d categories",
            len(TOLOKA_CATEGORIES),
        )
        for category in TOLOKA_CATEGORIES:
            if not self.running:
                break
            await self.process_category(category)
        logger.info("RefreshTopicsTask: full refresh complete")

    async def process_category(self, category):
        page = 0
        total = 0
        while self.running and (
            topics := await self.client.get_category_page_topics(category, page)
        ):
            logger.info("Category %s page %d: %d topics", category, page, len(topics))
            async with self.engine.begin() as conn:
                for topic in topics:
                    await upsert_topic(conn, topic_data=topic, category=category)
            total += len(topics)
            page += 1
        if total:
            logger.info("Category %s: upserted %d topics across %d pages", category, total, page)


class CheckNewTopicsTask(AbstractTask):
    def __init__(self, client, engine):
        self.client = client
        self.engine = engine

    async def run_once(self):
        recent_categories = await self.client.get_recent_categories()
        logger.info("CheckNewTopicsTask: checking %d recent categories", len(recent_categories))
        for category in recent_categories:
            if not self.running:
                break
            for sort in (0, 8):
                topics = await self.client.get_category_page_topics(category, 0, sort=sort)
                logger.info("Category %s sort=%d: %d topics", category, sort, len(topics))
                async with self.engine.begin() as conn:
                    for topic in topics:
                        await upsert_topic(conn, topic_data=topic, category=category)

        logger.info("CheckNewTopicsTask: waiting")
        for _ in range(10 * 60):
            if not self.running:
                return
            await asyncio.sleep(1)
