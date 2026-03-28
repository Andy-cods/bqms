"""ETL loader — runs on VPS host, reads JSON, inserts into PostgreSQL."""
import asyncio
import json
import time
import sys

import asyncpg
from datetime import date as Date


DSN = "postgresql://scadmin:SC2026_Pr0d_S3cure!@127.0.0.1:5432/songchau"
DATA_FILE = "/opt/songchau/data/etl_data.json"


def _clean(val):
    if val is None or val == "None" or val == "":
        return None
    return val


def _date(val):
    v = _clean(val)
    if v is None:
        return None
    try:
        parts = str(v)[:10].split("-")
        return Date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None


def _float(val):
    v = _clean(val)
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _int(val):
    v = _clean(val)
    if v is None:
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


async def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        rows = json.load(f)
    print(f"Loaded {len(rows)} rows from JSON")

    conn = await asyncpg.connect(DSN)

    inserted = skipped = errors = 0
    t0 = time.time()

    for i, row in enumerate(rows):
        try:
            r = await conn.execute(
                """INSERT INTO transactions
                   (transaction_date, rfq_no, bqms_code, spec, maker,
                    quantity, unit, price_rmb, price_vnd, price_quoted,
                    version, result, person_in_charge, notes,
                    source_file, source_sheet, source_row, row_hash)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
                   ON CONFLICT (row_hash) DO NOTHING""",
                _date(row.get("transaction_date")),
                _clean(row.get("rfq_no")),
                _clean(row.get("bqms_code")),
                _clean(row.get("spec")),
                _clean(row.get("maker")),
                _float(row.get("quantity")),
                _clean(row.get("unit")) or "EA",
                _float(row.get("price_rmb")),
                _float(row.get("price_vnd")),
                _float(row.get("price_quoted")),
                _clean(row.get("version")),
                _clean(row.get("result")),
                (_clean(row.get("person_in_charge")) or "")[:200] or None,
                (_clean(row.get("notes")) or "")[:500] or None,
                row.get("source_file"),
                row.get("source_sheet"),
                _int(row.get("source_row")),
                row.get("row_hash"),
            )
            if r == "INSERT 0 1":
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error row {i}: {e}")

        if (i + 1) % 10000 == 0:
            print(f"  Progress: {i+1}/{len(rows)} ({time.time()-t0:.0f}s)")

    print(f"Transactions: {inserted} inserted, {skipped} skipped, {errors} errors in {time.time()-t0:.0f}s")

    # Extract products
    r = await conn.execute("""
        INSERT INTO products (bqms_code, product_name, spec, maker, type, unit)
        SELECT DISTINCT ON (t.bqms_code)
            t.bqms_code,
            COALESCE(t.spec, t.bqms_code),
            t.spec,
            t.maker,
            CASE WHEN t.result = 'gc' THEN 'gc'
                 WHEN t.result = 'tm' THEN 'tm'
                 ELSE NULL END,
            COALESCE(t.unit, 'EA')
        FROM transactions t
        WHERE t.bqms_code IS NOT NULL AND t.bqms_code != ''
        ON CONFLICT (bqms_code) DO UPDATE SET
            spec = COALESCE(EXCLUDED.spec, products.spec),
            maker = COALESCE(EXCLUDED.maker, products.maker),
            updated_at = NOW()
    """)
    print(f"Products: {r}")

    tc = await conn.fetchval("SELECT COUNT(*) FROM transactions")
    pc = await conn.fetchval("SELECT COUNT(*) FROM products")
    print(f"Final: {tc} transactions, {pc} products")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
