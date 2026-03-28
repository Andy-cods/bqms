"""ETL Runner — extract Excel data and load into PostgreSQL.

Usage:
    python -m etl.runner --file "path/to/file.xlsm" --dry-run
    python -m etl.runner --all --onedrive "C:/Users/.../OneDrive - SONG CHAU CO., LTD"
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime

import asyncpg


async def load_transactions(conn: asyncpg.Connection, rows: list[dict]) -> dict:
    """Batch insert transactions with ON CONFLICT dedup."""
    inserted = 0
    skipped = 0
    errors = 0

    for row in rows:
        try:
            result = await conn.execute(
                """INSERT INTO transactions
                   (transaction_date, rfq_no, bqms_code, spec, maker,
                    quantity, unit, price_rmb, price_vnd, price_quoted,
                    version, result, person_in_charge, notes,
                    source_file, source_sheet, source_row, row_hash)
                   VALUES ($1::date, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                           $11, $12, $13, $14, $15, $16, $17, $18)
                   ON CONFLICT (row_hash) DO NOTHING""",
                row.get("transaction_date"),
                row.get("rfq_no"), row.get("bqms_code"),
                row.get("spec"), row.get("maker"),
                row.get("quantity"), row.get("unit", "EA"),
                row.get("price_rmb"), row.get("price_vnd"),
                row.get("price_quoted"), row.get("version"),
                row.get("result"), row.get("person_in_charge"),
                row.get("notes"), row.get("source_file"),
                row.get("source_sheet"), row.get("source_row"),
                row.get("row_hash"),
            )
            if result == "INSERT 0 1":
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error row {row.get('source_row')}: {e}")

    return {"inserted": inserted, "skipped": skipped, "errors": errors}


async def load_products_from_transactions(conn: asyncpg.Connection) -> int:
    """Extract unique products from transactions and upsert into products table."""
    result = await conn.execute("""
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
    # Extract count from result string like "INSERT 0 1234"
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0


async def log_etl_job(
    conn: asyncpg.Connection, job_type: str, source: str,
    status: str, rows_processed: int, rows_inserted: int,
    rows_skipped: int, errors_text: str,
) -> None:
    await conn.execute(
        """INSERT INTO etl_jobs
           (job_type, source_file, status, rows_processed, rows_inserted,
            rows_updated, rows_skipped, errors, finished_at)
           VALUES ($1, $2, $3, $4, $5, 0, $6, $7, NOW())""",
        job_type, source, status, rows_processed, rows_inserted,
        rows_skipped, errors_text,
    )


async def run_etl(args):
    from etl.extractors.tt_xnk import extract_file

    dsn = args.dsn or os.getenv(
        "DATABASE_URL",
        "postgresql://scadmin:SC2026_Pr0d_S3cure!@123.30.48.127:5432/songchau",
    )

    # Collect files to process
    files = []
    if args.file:
        files.append(args.file)
    elif args.all and args.onedrive:
        bqms_dir = os.path.join(args.onedrive, "Puplic", "BQMS")
        candidates = [
            os.path.join(bqms_dir, "TT XNK BQMS 2026.xlsm"),
            os.path.join(bqms_dir, "TT XNK BQMS 2025.xlsm"),
        ]
        for f in candidates:
            if os.path.exists(f):
                files.append(f)
            else:
                print(f"  Skip (not found): {f}")

    if not files:
        print("No files to process. Use --file or --all --onedrive")
        return

    print(f"ETL starting: {len(files)} file(s)")
    print(f"Database: {dsn.split('@')[1] if '@' in dsn else dsn}")
    print()

    total_extracted = 0
    total_inserted = 0
    total_skipped = 0
    total_errors = 0

    for filepath in files:
        fname = os.path.basename(filepath)
        print(f"[{fname}]")

        # Extract
        t0 = time.time()
        try:
            rows = extract_file(filepath)
        except Exception as e:
            print(f"  EXTRACT ERROR: {e}")
            continue
        extract_time = time.time() - t0
        print(f"  Extracted: {len(rows)} rows in {extract_time:.1f}s")
        total_extracted += len(rows)

        if args.dry_run:
            print("  DRY RUN — skipping load")
            if rows:
                print(f"  Sample row: {json.dumps({k: str(v)[:50] for k, v in rows[0].items()}, ensure_ascii=False)}")
            continue

        # Load
        t0 = time.time()
        conn = await asyncpg.connect(dsn)
        try:
            result = await load_transactions(conn, rows)
            total_inserted += result["inserted"]
            total_skipped += result["skipped"]
            total_errors += result["errors"]
            load_time = time.time() - t0
            print(f"  Loaded: {result['inserted']} inserted, {result['skipped']} skipped, {result['errors']} errors in {load_time:.1f}s")

            # Log ETL job
            await log_etl_job(
                conn, "tt_xnk", fname, "done",
                len(rows), result["inserted"], result["skipped"],
                f"{result['errors']} errors" if result["errors"] else "",
            )
        finally:
            await conn.close()

    # Extract products from transactions
    if not args.dry_run and total_inserted > 0:
        print("\n[Products extraction]")
        conn = await asyncpg.connect(dsn)
        try:
            products_count = await load_products_from_transactions(conn)
            print(f"  Upserted {products_count} products from transactions")
        finally:
            await conn.close()

    print(f"\n{'='*40}")
    print(f"Total: {total_extracted} extracted, {total_inserted} inserted, {total_skipped} skipped, {total_errors} errors")


def main():
    parser = argparse.ArgumentParser(description="Song Chau ETL Runner")
    parser.add_argument("--file", help="Path to specific Excel file")
    parser.add_argument("--all", action="store_true", help="Process all known files")
    parser.add_argument("--onedrive", help="OneDrive root path")
    parser.add_argument("--dsn", help="PostgreSQL DSN")
    parser.add_argument("--dry-run", action="store_true", help="Extract only, don't load")
    args = parser.parse_args()

    asyncio.run(run_etl(args))


if __name__ == "__main__":
    main()
