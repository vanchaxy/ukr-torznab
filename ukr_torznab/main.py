import asyncio
import gc
import logging
import os
import signal
from pathlib import Path

import httpx
import uvicorn
from sqlalchemy.ext.asyncio import create_async_engine

from ukr_torznab.api import app as api_app
from ukr_torznab.clients.toloka import TolokaClient
from ukr_torznab.db.tables import release, topic
from ukr_torznab.settings import (
    ALEMBIC_DATABASE_URL,
    API_PORT,
    DATABASE_URL,
    ELECTRIC_URL,
    OPENAI_API_KEY,
    QBITTORRENT_PASSWORD,
    QBITTORRENT_URL,
    QBITTORRENT_USERNAME,
    TOLOKA_PASSWORD,
    TOLOKA_USERNAME,
    UTP_API_KEY,
)
from ukr_torznab.tasks.base import AbstractTask

_MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", ALEMBIC_DATABASE_URL)
    command.upgrade(cfg, "head")


def _configure_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


async def main():
    _configure_logging()
    _run_migrations()
    gc.collect()

    engine = create_async_engine(DATABASE_URL, connect_args={"timeout": 30})

    toloka_client = TolokaClient(username=TOLOKA_USERNAME, password=TOLOKA_PASSWORD)
    await toloka_client.login()

    api_app.state.engine = engine
    api_app.state.toloka_client = toloka_client

    utp_client = None
    if UTP_API_KEY:
        from ukr_torznab.clients.utp import UtpClient

        utp_client = UtpClient(api_key=UTP_API_KEY)
        logging.getLogger(__name__).info("UTP client enabled")
    api_app.state.utp_client = utp_client

    tasks: list[AbstractTask] = []
    electric_client: httpx.AsyncClient | None = None
    skyhook_client = None
    servarr_client = None
    openai_client = None

    if ELECTRIC_URL:
        logging.getLogger(__name__).info(
            "Starting in consumer mode (ELECTRIC_URL=%s)",
            ELECTRIC_URL,
        )
        from ukr_torznab.tasks.consumer import ElectricConsumerTask

        electric_client = httpx.AsyncClient()
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
        logging.getLogger(__name__).info("Starting in scraper mode")
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
        servarr_client = ServarrClient()
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

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

    qbt_client = None
    if QBITTORRENT_URL:
        from ukr_torznab.clients.qbittorrent import QBittorrentClient
        from ukr_torznab.tasks.renamer import RenameTorrentsTask

        qbt_client = QBittorrentClient(QBITTORRENT_URL, QBITTORRENT_USERNAME, QBITTORRENT_PASSWORD)
        await qbt_client.login()
        tasks.append(
            RenameTorrentsTask(engine=engine, qbt_client=qbt_client, utp_client=utp_client),
        )

    for task in tasks:
        task.start()

    gc.collect()

    uvicorn_config = uvicorn.Config(api_app, host="0.0.0.0", port=API_PORT, log_level="warning")
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
    finally:
        await engine.dispose()
        await toloka_client.close()
        if skyhook_client is not None:
            await skyhook_client.close()
        if servarr_client is not None:
            await servarr_client.close()
        if openai_client is not None:
            await openai_client.close()
        if electric_client is not None:
            await electric_client.aclose()
        if qbt_client is not None:
            await qbt_client.close()
        if utp_client is not None:
            await utp_client.close()


if __name__ == "__main__":
    asyncio.run(main())
