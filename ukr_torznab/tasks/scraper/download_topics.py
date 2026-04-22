import logging
from datetime import datetime

from ukr_torznab.db.queries import get_topic_id_to_download, upsert_page
from ukr_torznab.tasks.base import AbstractTask

logger = logging.getLogger(__name__)


class DownloadTopicsTask(AbstractTask):
    def __init__(self, client, engine):
        self.client = client
        self.engine = engine

    async def run_once(self):
        async with self.engine.begin() as conn:
            topic_and_download_ids = await get_topic_id_to_download(conn)
            if not topic_and_download_ids:
                logger.info("No topics to download, sleeping")
                await self.interruptible_sleep(60)
                return

            topic_id, download_id = topic_and_download_ids
            logger.info("Downloading topic %s (download_id=%s)", topic_id, download_id)

            html = await self.client.download_topic(topic_id)
            if html is None:
                logger.warning("Topic %s: HTML download returned None", topic_id)
            else:
                logger.info("Topic %s: HTML downloaded (%d bytes)", topic_id, len(html))

            torrent = await self.client.download_torrent(download_id)
            if torrent is None:
                logger.warning(
                    "Topic %s: torrent download returned None (download_id=%s)",
                    topic_id,
                    download_id,
                )
            else:
                logger.info("Topic %s: torrent downloaded (%d bytes)", topic_id, len(torrent))

            await upsert_page(
                conn,
                id=topic_id,
                html=html,
                torrent=torrent,
                downloaded_at=datetime.now().astimezone(),
            )
            logger.info("Topic %s: page saved", topic_id)
