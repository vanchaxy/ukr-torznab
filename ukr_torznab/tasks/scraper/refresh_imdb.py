import logging
import time
import zlib

import httpx
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from ukr_torznab.db.tables import imdb_titles
from ukr_torznab.tasks.base import AbstractTask

logger = logging.getLogger(__name__)

TABLE_NAME = imdb_titles.name
TMP_TABLE_NAME = f"{TABLE_NAME}_tmp"
OLD_TABLE_NAME = f"{TABLE_NAME}_old"

_imdb_titles_tmp = imdb_titles.to_metadata(sa.MetaData(), name=TMP_TABLE_NAME)
_COLUMNS = [c.name for c in _imdb_titles_tmp.columns]

REFRESH_INTERVAL = 5 * 60 * 60
INSERT_BATCH_SIZE = 100_000


class RefreshImdbTask(AbstractTask):
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def run_once(self):
        async with self.engine.connect() as conn:
            existing_rows = (
                await conn.execute(sa.select(sa.func.count()).select_from(imdb_titles))
            ).scalar()
        if existing_rows:
            logger.info(
                "RefreshImdbTask: waiting %dh before next refresh",
                REFRESH_INTERVAL // 3600,
            )
            await self.interruptible_sleep(REFRESH_INTERVAL)
        else:
            logger.info("RefreshImdbTask: imdb_titles is empty, refreshing immediately")

        start = time.time()
        logger.info("RefreshImdbTask: dropping stale tmp/old tables")
        async with self.engine.begin() as conn:
            await conn.exec_driver_sql(f"DROP TABLE IF EXISTS {TMP_TABLE_NAME}")
            await conn.exec_driver_sql(f"DROP TABLE IF EXISTS {OLD_TABLE_NAME}")

        logger.info("RefreshImdbTask: creating temporary table (%.1fs)", time.time() - start)
        async with self.engine.begin() as conn:
            await conn.run_sync(imdb_titles.create, checkfirst=True)
            await conn.run_sync(_imdb_titles_tmp.create)

        logger.info("RefreshImdbTask: downloading IMDB titles dataset (%.1fs)", time.time() - start)
        batch: list[tuple] = []
        buffer = bytearray()
        gzip_decompressor = zlib.decompressobj(zlib.MAX_WBITS | 16)
        total_rows = 0

        async with (
            httpx.AsyncClient() as client,
            client.stream(
                "GET",
                "https://datasets.imdbws.com/title.basics.tsv.gz",
            ) as response,
        ):
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                buffer.extend(gzip_decompressor.decompress(chunk))
                batch.extend(self._drain_rows(buffer))
                if len(batch) >= INSERT_BATCH_SIZE:
                    total_rows += await self._insert_batch(batch)
                    batch = []

        buffer.extend(gzip_decompressor.flush())
        batch.extend(self._drain_rows(buffer))
        if batch:
            total_rows += await self._insert_batch(batch)

        logger.info(
            "RefreshImdbTask: download complete — %d rows inserted (%.1fs)",
            total_rows,
            time.time() - start,
        )

        logger.info("RefreshImdbTask: swapping tables (%.1fs)", time.time() - start)
        async with self.engine.begin() as conn:
            await conn.exec_driver_sql(
                f"ALTER TABLE {TABLE_NAME} RENAME TO {OLD_TABLE_NAME}",
            )
            await conn.exec_driver_sql(
                f"ALTER TABLE {TMP_TABLE_NAME} RENAME TO {TABLE_NAME}",
            )

        if self.engine.dialect.name == "sqlite":
            logger.info("RefreshImdbTask: running WAL checkpoint")
            async with self.engine.begin() as conn:
                await conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE);")

        logger.info("RefreshImdbTask: refresh complete (%.1fs)", time.time() - start)

    async def _insert_batch(self, batch: list[tuple]) -> int:
        async with self.engine.begin() as conn:
            await conn.execute(
                _imdb_titles_tmp.insert(),
                [dict(zip(_COLUMNS, r)) for r in batch],
            )
        return len(batch)

    def _drain_rows(self, buffer: bytearray) -> list[tuple]:
        """Consume complete lines from ``buffer`` and return the parsed rows."""
        rows = []
        while (pos := buffer.find(b"\n")) != -1:
            fields = buffer[:pos].decode("utf-8").split("\t")
            del buffer[: pos + 1]
            if fields and fields[0] == "tconst":
                continue
            row = self.parse_row(fields)
            if row:
                rows.append(row)
        return rows

    @staticmethod
    def parse_row(fields: list[str]):
        if len(fields) != 9:
            logger.warning(
                "Skipping malformed IMDB row (expected 9 fields, got %d): %s",
                len(fields),
                fields,
            )
            return None
        if not fields[0].startswith("tt"):
            logger.warning("Skipping malformed IMDB row (invalid tconst): %s", fields[0])
            return None

        def int_or_none(s):
            return None if s == "\\N" else int(s)

        return (
            int(fields[0][2:]),
            fields[1],
            fields[2],
            fields[3],
            int_or_none(fields[4]),
            int_or_none(fields[5]),
            int_or_none(fields[6]),
            int_or_none(fields[7]),
            fields[8],
        )
