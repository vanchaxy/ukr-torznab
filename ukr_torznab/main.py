import asyncio
import gc
import logging
import signal
from contextlib import AsyncExitStack
from pathlib import Path

import httpx
import uvicorn
from sqlalchemy.ext.asyncio import create_async_engine

from ukr_torznab import __version__
from ukr_torznab.api import app as api_app
from ukr_torznab.clients.toloka import TolokaClient
from ukr_torznab.db.tables import release, topic
from ukr_torznab.settings import (
    ALEMBIC_DATABASE_URL,
    API_PORT,
    DATABASE_URL,
    ELECTRIC_URL,
    LOG_LEVEL,
    OPENAI_API_KEY,
    QBITTORRENT_PASSWORD,
    QBITTORRENT_URL,
    QBITTORRENT_USERNAME,
    TOLOKA_PASSWORD,
    TOLOKA_USERNAME,
    UTP_API_KEY,
)
from ukr_torznab.tasks.base import AbstractTask

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", ALEMBIC_DATABASE_URL)
    command.upgrade(cfg, "head")


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


async def main():
    _configure_logging()
    _run_migrations()
    gc.collect()

    async with AsyncExitStack() as stack:
        engine = create_async_engine(DATABASE_URL, connect_args={"timeout": 30})
        stack.push_async_callback(engine.dispose)

        toloka_client = TolokaClient(username=TOLOKA_USERNAME, password=TOLOKA_PASSWORD)
        stack.push_async_callback(toloka_client.close)
        await toloka_client.login()

        api_app.state.engine = engine
        api_app.state.toloka_client = toloka_client

        utp_client = None
        if UTP_API_KEY:
            from ukr_torznab.clients.utp import UtpClient

            utp_client = UtpClient(api_key=UTP_API_KEY)
            stack.push_async_callback(utp_client.close)
            logger.info("UTP client enabled")
        api_app.state.utp_client = utp_client

        tasks: list[AbstractTask] = []

        if ELECTRIC_URL:
            logger.info("Starting in consumer mode (ELECTRIC_URL=%s)", ELECTRIC_URL)
            from ukr_torznab.tasks.consumer import ElectricConsumerTask

            electric_client = httpx.AsyncClient(
                headers={"User-Agent": f"ukr-torznab/{__version__}"},
            )
            stack.push_async_callback(electric_client.aclose)
            for table in (topic, release):
                tasks.append(
                    ElectricConsumerTask(
                        engine=engine,
                        client=electric_client,
                        electric_url=ELECTRIC_URL,
                        table=table,
                    ),
                )
        else:
            logger.info("Starting in scraper mode")
            from openai import AsyncOpenAI

            from ukr_torznab.clients.servarr import ServarrClient
            from ukr_torznab.clients.skyhook import SkyhookClient
            from ukr_torznab.tasks.scraper import (
                CheckNewTopicsTask,
                DownloadTopicsTask,
                ParseTopicsTask,
                RefreshImdbTask,
                RefreshTopicsTask,
            )

            skyhook_client = SkyhookClient()
            stack.push_async_callback(skyhook_client.close)
            servarr_client = ServarrClient()
            stack.push_async_callback(servarr_client.close)
            openai_client = None
            if OPENAI_API_KEY:
                openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
                stack.push_async_callback(openai_client.close)

            tasks = [
                CheckNewTopicsTask(client=toloka_client, engine=engine),
                RefreshTopicsTask(client=toloka_client, engine=engine),
                DownloadTopicsTask(client=toloka_client, engine=engine),
                RefreshImdbTask(engine=engine),
                ParseTopicsTask(
                    engine=engine,
                    skyhook_client=skyhook_client,
                    servarr_client=servarr_client,
                    openai_client=openai_client,
                ),
            ]

        if QBITTORRENT_URL:
            from ukr_torznab.clients.qbittorrent import QBittorrentClient
            from ukr_torznab.tasks.renamer import RenameTorrentsTask

            qbt_client = QBittorrentClient(
                QBITTORRENT_URL,
                QBITTORRENT_USERNAME,
                QBITTORRENT_PASSWORD,
            )
            stack.push_async_callback(qbt_client.close)
            await qbt_client.login()
            tasks.append(
                RenameTorrentsTask(engine=engine, qbt_client=qbt_client, utp_client=utp_client),
            )

        for task in tasks:
            task.start()

        gc.collect()

        uvicorn_config = uvicorn.Config(
            api_app,
            host="0.0.0.0",
            port=API_PORT,
            log_level="warning",
        )
        uvicorn_server = uvicorn.Server(uvicorn_config)

        async def stop_handler():
            uvicorn_server.should_exit = True
            await asyncio.gather(*[task.close() for task in tasks])

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(stop_handler()))

        try:
            await asyncio.gather(
                uvicorn_server.serve(),
                *[task.wait() for task in tasks],
            )
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
