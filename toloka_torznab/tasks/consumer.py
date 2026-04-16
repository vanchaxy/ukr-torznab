from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

import httpx
import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine

from toloka_torznab.db.tables import electric_offset
from toloka_torznab.db.upsert import upsert
from toloka_torznab.tasks.base import AbstractTask

logger = logging.getLogger(__name__)


def _coerce_row(table: sa.Table, row: dict) -> dict:
    """Coerce Electric JSON values to Python types expected by SQLAlchemy.

    Only includes columns that are actually present in *row* — Electric sends
    partial payloads on update operations.
    """
    result = {}
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
    """Subscribes to a single Electric shape and writes changes to the local DB."""

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
            exit()

        response.raise_for_status()

        new_handle = response.headers.get("electric-handle", current_handle)
        new_offset = response.headers.get("electric-offset", current_offset)
        messages: list[dict] = response.json()

        pk_col = _pk_col(self.table)
        ops: list[tuple[str, object]] = []

        for msg in messages:
            op_headers = msg.get("headers", {})
            if "control" in op_headers:
                continue
            operation = op_headers.get("operation")
            value = msg.get("value", {})
            if operation == "insert":
                ops.append(("insert", _coerce_row(self.table, value)))
            elif operation == "update":
                ops.append(("update", _coerce_row(self.table, value)))
            elif operation == "delete":
                ops.append(("delete", value.get(pk_col.name)))

        async with self.engine.begin() as conn:
            for op_type, op_data in ops:
                if op_type == "insert":
                    row_data = op_data
                    await conn.execute(
                        upsert(self.table, conn)
                        .values(row_data)
                        .on_conflict_do_update(
                            index_elements=[pk_col.name],
                            set_={k: v for k, v in row_data.items() if k != pk_col.name},
                        ),
                    )
                elif op_type == "update":
                    row_data = op_data
                    pk_val = row_data.get(pk_col.name)
                    update_data = {k: v for k, v in row_data.items() if k != pk_col.name}
                    if pk_val is not None and update_data:
                        await conn.execute(
                            self.table.update().where(pk_col == pk_val).values(update_data),
                        )
                else:
                    pk_val = op_data
                    if pk_val is not None:
                        await conn.execute(delete(self.table).where(pk_col == pk_val))

            offset_values = {"handle": new_handle, "offset": new_offset}
            await conn.execute(
                upsert(electric_offset, conn)
                .values({"shape_name": self.shape_name, **offset_values})
                .on_conflict_do_update(
                    index_elements=["shape_name"],
                    set_=offset_values,
                ),
            )
