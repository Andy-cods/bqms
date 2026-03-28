"""Product repository — trigram search, CRUD."""

from typing import Optional

from .base import BaseRepository


class ProductRepository(BaseRepository):

    async def search(
        self, q: str = "", type_filter: str = "",
        page: int = 1, limit: int = 50,
    ) -> tuple[list[dict], int]:
        conditions, params, idx = [], [], 1

        if q:
            conditions.append(
                f"(product_name ILIKE ${idx} OR spec ILIKE ${idx} "
                f"OR bqms_code ILIKE ${idx} OR maker ILIKE ${idx})"
            )
            params.append(f"%{q}%")
            idx += 1
        if type_filter:
            conditions.append(f"type = ${idx}")
            params.append(type_filter)
            idx += 1

        where = " AND ".join(conditions) if conditions else ""
        return await self._fetch_page(
            "products", page, limit, where, params, "updated_at DESC",
        )

    async def get_by_id(self, product_id: int) -> Optional[dict]:
        row = await self.conn.fetchrow(
            "SELECT * FROM products WHERE id = $1", product_id,
        )
        return dict(row) if row else None

    async def create(self, data: dict) -> dict:
        row = await self.conn.fetchrow(
            """INSERT INTO products
               (bqms_code, product_name, spec, maker, category, unit, type, min_stock, current_stock)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
               RETURNING *""",
            data.get("bqms_code"), data["product_name"], data.get("spec"),
            data.get("maker"), data.get("category"), data.get("unit", "EA"),
            data.get("type"), data.get("min_stock", 0), data.get("current_stock", 0),
        )
        return dict(row)

    async def update(self, product_id: int, data: dict) -> Optional[dict]:
        sets, params, idx = ["updated_at = NOW()"], [], 1
        for key in ("product_name", "spec", "maker", "category", "unit", "type", "min_stock", "current_stock"):
            if key in data and data[key] is not None:
                sets.append(f"{key} = ${idx}")
                params.append(data[key])
                idx += 1
        params.append(product_id)
        sql = f"UPDATE products SET {', '.join(sets)} WHERE id = ${idx} RETURNING *"
        row = await self.conn.fetchrow(sql, *params)
        return dict(row) if row else None

    async def delete(self, product_id: int) -> bool:
        result = await self.conn.execute(
            "DELETE FROM products WHERE id = $1", product_id,
        )
        return result == "DELETE 1"

    async def count(self) -> int:
        return await self.conn.fetchval("SELECT COUNT(*) FROM products") or 0

    async def count_by_type(self) -> dict:
        rows = await self.conn.fetch(
            "SELECT type, COUNT(*) as cnt FROM products GROUP BY type"
        )
        return {r["type"] or "unknown": r["cnt"] for r in rows}
