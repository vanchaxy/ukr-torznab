import asyncio
import logging
from datetime import date, datetime

import httpx
import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ukr_torznab.db.tables import electric_offset
from ukr_torznab.db.upsert import upsert
from ukr_torznab.tasks.base import AbstractTask

logger = logging.getLogger(__name__)


def _coerce_row(table: sa.Table, row: dict) -> dict:
    result: dict[str, object] = {}
    for col in table.columns:
        if col.name not in row:
            continue
        val = row[col.name]
        if val is None:
            result[col.name] = None
        elif isinstance(col.type, sa.Boolean):
            if isinstance(val, bool):
                result[col.name] = val
            else:
                result[col.name] = str(val).lower() in ("t", "true", "1")
        elif isinstance(col.type, sa.Date):
            result[col.name] = date.fromisoformat(val)
        elif isinstance(col.type, sa.DateTime):
            result[col.name] = datetime.fromisoformat(val)
        else:
            result[col.name] = val
    return result


def _pk_col(table: sa.Table) -> sa.Column:
    return next(c for c in table.columns if c.primary_key)


class ElectricConsumerTask(AbstractTask):
    def __init__(
        self,
        engine: AsyncEngine,
        client: httpx.AsyncClient,
        electric_url: str,
        table: sa.Table,
    ):
        self.engine = engine
        self.client = client
        self.electric_url = electric_url.rstrip("/")
        self.table = table
        self.shape_name = table.name

    async def run_once(self):
        async with self.engine.begin() as conn:
            row = (
                await conn.execute(
                    select(electric_offset).where(electric_offset.c.shape_name == self.shape_name),
                )
            ).first()

        current_offset = row.offset if row else "-1"
        current_handle = row.handle if row else None

        params: dict = {"table": self.shape_name, "offset": current_offset}
        if current_handle:
            params["handle"] = current_handle
        if current_offset != "-1":
            params["live"] = "true"

        try:
            response = await self.client.get(
                f"{self.electric_url}/v1/shape",
                params=params,
                timeout=60.0,
            )
        except httpx.RequestError as exc:
            logger.warning(
                "Electric request failed for %s: %s: %s",
                self.shape_name,
                type(exc).__name__,
                exc,
            )
            await asyncio.sleep(60)
            return

        if response.status_code in (400, 409):
            logger.warning(
                "Electric returned %d for %s (handle invalidated), resetting shape",
                response.status_code,
                self.shape_name,
            )
            async with self.engine.begin() as conn:
                await conn.execute(delete(self.table))
                await conn.execute(
                    delete(electric_offset).where(electric_offset.c.shape_name == self.shape_name),
                )
            # Exit so the process restarts, re-runs migrations and resyncs the shape from scratch.
            raise SystemExit(f"Electric shape {self.shape_name!r} was reset; restart to resync")

        response.raise_for_status()

        new_handle = response.headers.get("electric-handle", current_handle)
        new_offset = response.headers.get("electric-offset", current_offset)
        messages: list[dict] = response.json()

        async with self.engine.begin() as conn:
            for msg in messages:
                await self._apply_message(conn, msg)

            offset_values = {"handle": new_handle, "offset": new_offset}
            await conn.execute(
                upsert(electric_offset, conn)
                .values({"shape_name": self.shape_name, **offset_values})
                .on_conflict_do_update(
                    index_elements=["shape_name"],
                    set_=offset_values,
                ),
            )

    async def _apply_message(self, conn: AsyncConnection, msg: dict) -> None:
        headers = msg.get("headers", {})
        if "control" in headers:
            return
        operation = headers.get("operation")
        value = msg.get("value", {})
        pk_col = _pk_col(self.table)

        if operation == "insert":
            row = _coerce_row(self.table, value)
            await conn.execute(
                upsert(self.table, conn)
                .values(row)
                .on_conflict_do_update(
                    index_elements=[pk_col.name],
                    set_={k: v for k, v in row.items() if k != pk_col.name},
                ),
            )
        elif operation == "update":
            row = _coerce_row(self.table, value)
            pk_val = row.get(pk_col.name)
            update_data = {k: v for k, v in row.items() if k != pk_col.name}
            if pk_val is not None and update_data:
                await conn.execute(
                    self.table.update().where(pk_col == pk_val).values(update_data),
                )
        elif operation == "delete":
            pk_val = value.get(pk_col.name)
            if pk_val is not None:
                await conn.execute(delete(self.table).where(pk_col == pk_val))
