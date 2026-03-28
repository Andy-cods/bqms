"""Purchase Order repository."""

from typing import Optional
from uuid import UUID

from .base import BaseRepository


class PORepository(BaseRepository):

    async def search(
        self, status: str = "", supplier_id: int = 0,
        page: int = 1, limit: int = 50,
    ) -> tuple[list[dict], int]:
        conditions, params, idx = [], [], 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if supplier_id:
            conditions.append(f"supplier_id = ${idx}")
            params.append(supplier_id)
            idx += 1
        where = " AND ".join(conditions) if conditions else ""
        return await self._fetch_page(
            "purchase_orders", page, limit, where, params, "created_at DESC",
        )

    async def get_by_id(self, po_id: int) -> Optional[dict]:
        row = await self.conn.fetchrow(
            "SELECT * FROM purchase_orders WHERE id = $1", po_id,
        )
        return dict(row) if row else None

    async def create(self, data: dict, created_by: UUID) -> dict:
        row = await self.conn.fetchrow(
            """INSERT INTO purchase_orders
               (po_number, supplier_id, total_amount, currency, eta_date, notes, created_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *""",
            data["po_number"], data.get("supplier_id"), data.get("total_amount"),
            data.get("currency", "VND"), data.get("eta_date"),
            data.get("notes"), created_by,
        )
        return dict(row)

    async def update_status(
        self, po_id: int, status: str,
        approved_by: Optional[UUID] = None,
    ) -> Optional[dict]:
        if approved_by:
            row = await self.conn.fetchrow(
                """UPDATE purchase_orders
                   SET status=$1, approved_by=$2, approved_at=NOW(), updated_at=NOW()
                   WHERE id=$3 RETURNING *""",
                status, approved_by, po_id,
            )
        else:
            row = await self.conn.fetchrow(
                "UPDATE purchase_orders SET status=$1, updated_at=NOW() WHERE id=$2 RETURNING *",
                status, po_id,
            )
        return dict(row) if row else None

    async def get_line_items(self, po_id: int) -> list[dict]:
        rows = await self.conn.fetch(
            "SELECT * FROM po_line_items WHERE po_id = $1", po_id,
        )
        return [dict(r) for r in rows]

    async def add_line_item(self, po_id: int, item: dict) -> dict:
        total = (item.get("quantity", 0) or 0) * (item.get("unit_price", 0) or 0)
        row = await self.conn.fetchrow(
            """INSERT INTO po_line_items
               (po_id, product_id, bqms_code, spec, quantity, unit_price, total_price, notes)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *""",
            po_id, item.get("product_id"), item.get("bqms_code"),
            item.get("spec"), item["quantity"], item.get("unit_price"),
            total, item.get("notes"),
        )
        return dict(row)

    async def count(self) -> int:
        return await self.conn.fetchval("SELECT COUNT(*) FROM purchase_orders") or 0
