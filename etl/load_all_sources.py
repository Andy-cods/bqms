"""Load all extracted data sources into PostgreSQL."""
import asyncio
import json
import time
from datetime import date as Date

import asyncpg

DSN = "postgresql://scadmin:SC2026_Pr0d_S3cure!@127.0.0.1:5432/songchau"
DATA_FILE = "/opt/songchau/data/etl_all_sources.json"


def _c(v):
    if v is None or v == "None" or v == "":
        return None
    return v

def _f(v):
    v = _c(v)
    return float(v) if v is not None else None

def _i(v):
    v = _c(v)
    return int(float(v)) if v is not None else None

def _dt(v):
    v = _c(v)
    if v is None: return None
    try:
        p = str(v)[:10].split("-")
        return Date(int(p[0]), int(p[1]), int(p[2]))
    except: return None

def _b(v):
    if isinstance(v, bool): return v
    return str(v).lower() in ("true", "1", "yes") if v else False


async def load_table(conn, table, rows, columns, converters):
    """Generic batch loader."""
    inserted = skipped = errors = 0
    placeholders = ",".join(f"${i+1}" for i in range(len(columns)))
    cols = ",".join(columns)
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT (row_hash) DO NOTHING"

    for row in rows:
        try:
            vals = [conv(row.get(col)) for col, conv in zip(columns, converters)]
            r = await conn.execute(sql, *vals)
            if r == "INSERT 0 1": inserted += 1
            else: skipped += 1
        except Exception as e:
            errors += 1
            if errors <= 3: print(f"  ERR: {e}")
    return inserted, skipped, errors


async def load_contacts(conn, rows):
    """Load contacts (no row_hash)."""
    inserted = 0
    for row in rows:
        email = _c(row.get("email"))
        name = _c(row.get("full_name"))
        if not email and not name: continue
        try:
            await conn.execute(
                "INSERT INTO contacts (email, full_name, delivery_info, phone, source_file) "
                "VALUES ($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",
                email, name, _c(row.get("delivery_info")), _c(row.get("phone")), _c(row.get("source_file"))
            )
            inserted += 1
        except: pass
    return inserted


async def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    conn = await asyncpg.connect(DSN)
    t0 = time.time()

    # 1. Quotations
    if "quotations" in data and data["quotations"]:
        cols = ["date","person_in_charge","rfq_no","bqms_code","spec","maker",
                "quantity_forecast","price_rmb","price_vnd","price_ama",
                "price_bqms_v1","price_bqms_v2","price_bqms_v3","price_bqms_v4",
                "notes","supplier","result","report","source_file","source_sheet","source_row","row_hash"]
        convs = [_dt,_c,_c,_c,_c,_c,_f,_f,_f,_f,_f,_f,_f,_f,_c,_c,_c,_c,_c,_c,_i,_c]
        i,s,e = await load_table(conn, "quotations", data["quotations"], cols, convs)
        print(f"quotations: {i} ins, {s} skip, {e} err")

    # 2. Quotation details
    if "quotation_details" in data and data["quotation_details"]:
        cols = ["person_in_charge","rfq_no","bqms_code","description","spec",
                "quantity_forecast","unit","price_po","po_deadline","notes",
                "supplier","hs_code","desc_import","source_file","source_row","row_hash"]
        convs = [_c,_c,_c,_c,_c,_f,_c,_f,_c,_c,_c,_c,_c,_c,_i,_c]
        i,s,e = await load_table(conn, "quotation_details", data["quotation_details"], cols, convs)
        print(f"quotation_details: {i} ins, {s} skip, {e} err")

    # 3. PO Deliveries
    for key in [k for k in data if k.startswith("deliveries_")]:
        if not data[key]: continue
        cols = ["po_date","po_number","shipping_no","rfq_no","bqms_code","spec",
                "quantity","unit","unit_price","total_amount","buyer","mail_pur",
                "receiver_name","warehouse","pur_phone","status","delivery_date",
                "actual_qty","delivery_info","delivery_method","origin",
                "total_delivered_vnd","source_file","source_row","row_hash"]
        convs = [_dt,_c,_c,_c,_c,_c,_f,_c,_f,_f,_c,_c,_c,_c,_c,_c,_dt,_f,_c,_c,_c,_f,_c,_i,_c]
        i,s,e = await load_table(conn, "po_deliveries", data[key], cols, convs)
        print(f"{key}: {i} ins, {s} skip, {e} err")

    # 4. Contacts
    for key in [k for k in data if k.startswith("contacts_")]:
        if not data[key]: continue
        i = await load_contacts(conn, data[key])
        print(f"{key}: {i} contacts loaded")

    # 5. Orders
    if "orders" in data and data["orders"]:
        cols = ["order_no","rfq_no","bqms_code","spec","customer",
                "quantity_planned","quantity_ordered","unit","order_date",
                "validity_period","status","quantity_delivered","delivery_date",
                "notes","source_file","source_row","row_hash"]
        convs = [_i,_c,_c,_c,_c,_f,_f,_c,_dt,_c,_c,_f,_dt,_c,_c,_i,_c]
        i,s,e = await load_table(conn, "order_tracking", data["orders"], cols, convs)
        print(f"orders: {i} ins, {s} skip, {e} err")

    # 6. Monthly reports
    if "monthly" in data and data["monthly"]:
        cols = ["year","month","row_no","folder_name","quotation_no","description",
                "quantity_forecast","tech_specs","unit","quote_price","quote_value",
                "currency","moq","product_code","image_ref","withdrew","free_sample",
                "cis_code","supplier","part_number","leadtime","input_date","end_date",
                "source_file","source_row","row_hash"]
        convs = [_i,_i,_i,_c,_c,_c,_f,_c,_c,_f,_f,_c,_f,_c,_c,_b,_b,_c,_c,_c,_c,_dt,_dt,_c,_i,_c]
        i,s,e = await load_table(conn, "monthly_input_data", data["monthly"], cols, convs)
        print(f"monthly: {i} ins, {s} skip, {e} err")

    # Summary
    tables = ["transactions","products","quotations","quotation_details",
              "po_deliveries","order_tracking","monthly_input_data","contacts"]
    print(f"\n{'='*50}")
    print(f"FINAL DATABASE STATE ({time.time()-t0:.0f}s):")
    for t in tables:
        cnt = await conn.fetchval(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t}: {cnt:,}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
