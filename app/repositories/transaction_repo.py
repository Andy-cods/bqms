"""Transaction repository — list, search, create."""

from .base import BaseRepository


class TransactionRepository(BaseRepository):

    async def search(
        self, q: str = "", date_from: str = "", date_to: str = "",
        page: int = 1, limit: int = 50,
    ) -> tuple[list[dict], int]:
        conditions, params, idx = [], [], 1

        if q:
            conditions.append(
                f"(bqms_code ILIKE ${idx} OR spec ILIKE ${idx} "
                f"OR rfq_no ILIKE ${idx} OR maker ILIKE ${idx})"
            )
            params.append(f"%{q}%")
            idx += 1
        if date_from:
            conditions.append(f"transaction_date >= ${idx}::date")
            params.append(date_from)
            idx += 1
        if date_to:
            conditions.append(f"transaction_date <= ${idx}::date")
            params.append(date_to)
            idx += 1

        where = " AND ".join(conditions) if conditions else ""
        return await self._fetch_page(
            "transactions", page, limit, where, params,
            "transaction_date DESC NULLS LAST",
        )

    async def create_batch(self, rows: list[dict]) -> int:
        inserted = 0
        for row in rows:
            try:
                await self.conn.execute(
                    """INSERT INTO transactions
                       (transaction_date, rfq_no, bqms_code, spec, maker,
                        quantity, unit, price_rmb, price_vnd, price_quoted,
                        version, result, person_in_charge, source_file, source_sheet,
                        source_row, row_hash)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
                       ON CONFLICT (row_hash) DO NOTHING""",
                    row.get("transaction_date"), row.get("rfq_no"),
                    row.get("bqms_code"), row.get("spec"), row.get("maker"),
                    row.get("quantity"), row.get("unit", "EA"),
                    row.get("price_rmb"), row.get("price_vnd"),
                    row.get("price_quoted"), row.get("version"),
                    row.get("result"), row.get("person_in_charge"),
                    row.get("source_file"), row.get("source_sheet"),
                    row.get("source_row"), row.get("row_hash"),
                )
                inserted += 1
            except Exception:
                continue
        return inserted

    async def count(self) -> int:
        return await self.conn.fetchval("SELECT COUNT(*) FROM transactions") or 0
