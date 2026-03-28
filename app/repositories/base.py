"""Base repository with common CRUD operations."""

from typing import Optional
import asyncpg


class BaseRepository:
    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def _fetch_page(
        self,
        table: str,
        page: int = 1,
        limit: int = 50,
        where: str = "",
        params: list | None = None,
        order_by: str = "created_at DESC",
    ) -> tuple[list[dict], int]:
        params = params or []
        limit = min(limit, 100)
        offset = (page - 1) * limit

        where_clause = f"WHERE {where}" if where else ""
        idx = len(params) + 1

        count_sql = f"SELECT COUNT(*) FROM {table} {where_clause}"
        total = await self.conn.fetchval(count_sql, *params)

        data_sql = (
            f"SELECT * FROM {table} {where_clause} "
            f"ORDER BY {order_by} LIMIT ${idx} OFFSET ${idx + 1}"
        )
        rows = await self.conn.fetch(data_sql, *params, limit, offset)

        return [dict(r) for r in rows], total or 0
