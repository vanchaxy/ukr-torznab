import logging

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from ukr_torznab.clients.toloka import TolokaClient
from ukr_torznab.db.queries import upsert_topic
from ukr_torznab.db.tables import topic as topic_table
from ukr_torznab.settings import TOLOKA_CATEGORIES
from ukr_torznab.tasks.base import AbstractTask

logger = logging.getLogger(__name__)


class RefreshTopicsTask(AbstractTask):
    def __init__(self, client: TolokaClient, engine: AsyncEngine):
        self.client = client
        self.engine = engine

    async def run_once(self):
        async with self.engine.connect() as conn:
            topic_count = (
                await conn.execute(sa.select(sa.func.count()).select_from(topic_table))
            ).scalar()
        if topic_count and topic_count >= 30_000:
            logger.info("RefreshTopicsTask: waiting before full category refresh")
            await self.interruptible_sleep(10 * 60 * 60)
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
    def __init__(self, client: TolokaClient, engine: AsyncEngine):
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
        await self.interruptible_sleep(10 * 60)
