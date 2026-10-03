"""Allowlisted, read-only SuperAdmin Database Console."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from data.superadmin_table_policy import (
    TablePolicy,
    console_policies,
    is_secret_column,
    require_policy,
)

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_LIMIT = 50


def quote_ident(name: str) -> str:
    if not IDENT_RE.match(name or ""):
        raise HTTPException(status_code=400, detail="Invalid identifier.")
    return f'"{name}"'


def qualify(schema: str, table: str) -> str:
    return f"{quote_ident(schema)}.{quote_ident(table)}"


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, memoryview)):
        return f"<binary {len(bytes(value))} bytes>"
    return value


def map_db_error(exc: Exception) -> HTTPException:
    orig = str(getattr(exc, "orig", exc)).lower()
    if "foreign key" in orig:
        return HTTPException(
            status_code=409,
            detail="This change conflicts with related records. No data was partially saved.",
        )
    if "unique" in orig or "duplicate" in orig:
        return HTTPException(status_code=409, detail="A record with this value already exists.")
    if "not-null" in orig or "not null" in orig or "null value" in orig:
        return HTTPException(status_code=400, detail="A required field is missing.")
    if "check constraint" in orig:
        return HTTPException(status_code=400, detail="The value does not meet a data rule.")
    return HTTPException(status_code=400, detail="The database rejected this change.")


class SuperAdminDatabaseService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_tables(self) -> list[dict[str, Any]]:
        tables: list[dict[str, Any]] = []
        for policy in console_policies():
            try:
                count = await self.db.scalar(text(f"SELECT COUNT(*) FROM {qualify(policy.schema, policy.name)}"))
            except SQLAlchemyError:
                count = 0
            tables.append(
                {
                    "schema": policy.schema,
                    "name": policy.name,
                    "label": policy.label,
                    "rows": int(count or 0),
                    "access": policy.access.value,
                    "notes": policy.notes,
                }
            )
        return tables

    async def columns(self, policy: TablePolicy) -> list[dict[str, Any]]:
        result = await self.db.execute(
            text(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = :schema AND table_name = :table
                ORDER BY ordinal_position
                """
            ),
            {"schema": policy.schema, "table": policy.name},
        )
        hidden = set(policy.hidden_columns)
        visible = set(policy.visible_columns) if policy.visible_columns else None
        columns = []
        for row in result:
            name = row.column_name
            if is_secret_column(name) or name in hidden:
                continue
            if visible is not None and name not in visible:
                continue
            columns.append(
                {
                    "name": name,
                    "data_type": row.data_type,
                    "nullable": row.is_nullable == "YES",
                    "editable": False,
                }
            )
        return columns

    async def list_rows(
        self,
        schema: str,
        table: str,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
    ) -> dict[str, Any]:
        policy = require_policy(schema, table, write=False)
        limit = max(1, min(limit, MAX_LIMIT))
        offset = max(0, offset)
        columns = await self.columns(policy)
        if not columns:
            raise HTTPException(status_code=404, detail="No visible columns for this table.")
        select_list = ", ".join(quote_ident(col["name"]) for col in columns)
        qualified = qualify(policy.schema, policy.name)
        where = ""
        search_params: dict[str, Any] = {}
        query = (search or "").strip()
        if query and policy.searchable:
            like = f"%{query}%"
            parts = []
            for index, column in enumerate(policy.searchable):
                if is_secret_column(column):
                    continue
                key = f"q{index}"
                parts.append(f"CAST({quote_ident(column)} AS TEXT) ILIKE :{key}")
                search_params[key] = like
            if parts:
                where = " WHERE " + " OR ".join(parts)
        try:
            total = int(
                await self.db.scalar(text(f"SELECT COUNT(*) FROM {qualified}{where}"), search_params)
                or 0
            )
            result = await self.db.execute(
                text(f"SELECT {select_list} FROM {qualified}{where} LIMIT :limit OFFSET :offset"),
                {**search_params, "limit": limit, "offset": offset},
            )
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to read this table right now.",
            ) from exc
        pk = await self._primary_key(policy.schema, policy.name)
        rows = []
        for mapping in result.mappings():
            data = {key: json_safe(value) for key, value in mapping.items()}
            row_id = str(data[pk[0]]) if len(pk) == 1 and pk[0] in data else None
            rows.append({"id": row_id, "data": data})
        return {
            "schema": policy.schema,
            "table": policy.name,
            "label": policy.label,
            "access": policy.access.value,
            "notes": policy.notes,
            "primary_key": pk,
            "total": total,
            "limit": limit,
            "offset": offset,
            "columns": columns,
            "rows": rows,
        }

    async def _primary_key(self, schema: str, table: str) -> list[str]:
        result = await self.db.execute(
            text(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = :schema
                  AND tc.table_name = :table
                ORDER BY kcu.ordinal_position
                """
            ),
            {"schema": schema, "table": table},
        )
        return [row[0] for row in result.all()]
