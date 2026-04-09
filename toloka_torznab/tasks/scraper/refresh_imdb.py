import asyncio
import logging
import time
import zlib

import httpx
import sqlalchemy as sa

from toloka_torznab.tasks.base import AbstractTask

logger = logging.getLogger(__name__)

TABLE_NAME = "imdb_titles"
TMP_TABLE_NAME = f"{TABLE_NAME}_tmp"
OLD_TABLE_NAME = f"{TABLE_NAME}_old"

_tmp_meta = sa.MetaData()
_imdb_titles_tmp = sa.Table(
    TMP_TABLE_NAME,
    _tmp_meta,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("title_type", sa.Text, nullable=True),
    sa.Column("primary_title", sa.Text, nullable=True),
    sa.Column("original_title", sa.Text, nullable=True),
    sa.Column("is_adult", sa.Integer, nullable=True),
    sa.Column("start_year", sa.Integer, nullable=True),
    sa.Column("end_year", sa.Integer, nullable=True),
    sa.Column("runtime_minutes", sa.Integer, nullable=True),
    sa.Column("genres", sa.Text, nullable=True),
)
_COLUMNS = [c.name for c in _imdb_titles_tmp.columns]

_imdb_titles_main = sa.Table(
    TABLE_NAME,
    _tmp_meta,
    *[col.copy() for col in _imdb_titles_tmp.columns],
)

REFRESH_INTERVAL = 5 * 60 * 60
INSERT_BATCH_SIZE = 100_000


class RefreshImdbTask(AbstractTask):
    def __init__(self, engine):
        self.engine = engine

    async def run_once(self):
        start = time.time()
        logger.info("RefreshImdbTask: dropping stale tmp/old tables")
        async with self.engine.begin() as conn:
            await conn.exec_driver_sql(f"DROP TABLE IF EXISTS {TMP_TABLE_NAME}")
            await conn.exec_driver_sql(f"DROP TABLE IF EXISTS {OLD_TABLE_NAME}")

        logger.info("RefreshImdbTask: creating temporary table (%.1fs)", time.time() - start)
        async with self.engine.begin() as conn:
            await conn.run_sync(_imdb_titles_main.create, checkfirst=True)
            await conn.run_sync(_imdb_titles_tmp.create)

        logger.info("RefreshImdbTask: downloading IMDB titles dataset (%.1fs)", time.time() - start)
        batch = []
        buffer = bytearray()
        is_first_line = True
        gzip_decompressor = zlib.decompressobj(zlib.MAX_WBITS | 16)
        total_rows = 0
        batches_inserted = 0

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
                while (pos := buffer.find(b"\n")) != -1:
                    fields = buffer[:pos].decode("utf-8").split("\t")
                    del buffer[: pos + 1]
                    if is_first_line:
                        is_first_line = False
                        if fields and fields[0] == "tconst":
                            continue
                    row = self.parse_row(fields)
                    if row:
                        batch.append(row)

                    if len(batch) >= INSERT_BATCH_SIZE:
                        async with self.engine.begin() as conn:
                            await conn.execute(
                                _imdb_titles_tmp.insert(),
                                [dict(zip(_COLUMNS, r)) for r in batch],
                            )
                        total_rows += len(batch)
                        batches_inserted += 1
                        batch = []

        buffer.extend(gzip_decompressor.flush())
        while (pos := buffer.find(b"\n")) != -1:
            fields = buffer[:pos].decode("utf-8").split("\t")
            row = self.parse_row(fields)
            if row:
                batch.append(row)
            del buffer[: pos + 1]

        if batch:
            async with self.engine.begin() as conn:
                await conn.execute(
                    _imdb_titles_tmp.insert(),
                    [dict(zip(_COLUMNS, r)) for r in batch],
                )
            total_rows += len(batch)

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

        logger.info("RefreshImdbTask: waiting %dh before next refresh", REFRESH_INTERVAL // 3600)
        for _ in range(REFRESH_INTERVAL):
            if not self.running:
                return
            await asyncio.sleep(1)

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
