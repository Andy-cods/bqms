"""Audit log + generic count repositories."""

from typing import Optional
from uuid import UUID

from .base import BaseRepository


class AuditRepository(BaseRepository):

    async def log(
        self, user_id: Optional[UUID], action: str,
        table_name: str = "", record_id: str = "",
        old_data: Optional[dict] = None, new_data: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        import json
        await self.conn.execute(
            """INSERT INTO audit_log
               (user_id, action, table_name, record_id, old_data, new_data, ip_address)
               VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7::inet)""",
            user_id, action, table_name, record_id,
            json.dumps(old_data) if old_data else None,
            json.dumps(new_data) if new_data else None,
            ip_address,
        )

    async def list_recent(self, page: int = 1, limit: int = 50) -> tuple[list[dict], int]:
        return await self._fetch_page(
            "audit_log", page, limit, order_by="created_at DESC",
        )


class StatsRepository(BaseRepository):

    async def get_all_counts(self) -> dict:
        tables = [
            "transactions", "products", "purchase_orders",
            "rfq", "deliveries", "market_prices", "users",
        ]
        counts = {}
        for t in tables:
            try:
                counts[t] = await self.conn.fetchval(f"SELECT COUNT(*) FROM {t}") or 0
            except Exception:
                counts[t] = 0
        return counts
