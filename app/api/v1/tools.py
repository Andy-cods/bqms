"""Tool endpoints — Auto-fill, AI Classify, Market Search, Dashboard KPIs."""

from fastapi import APIRouter, Depends

from ...db.session import get_db
from ...domain.enums import UserRole
from ...domain.exceptions import NotFoundError
from ..deps import get_current_user, require_role

router = APIRouter(prefix="/tools", tags=["tools"])


# ── Tool 1: Auto-fill ──────────────────────────────────

@router.post("/autofill")
async def autofill_match(
    items: list[dict], conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    results = []
    for item in items[:200]:
        spec = item.get("spec", "")
        bqms = item.get("bqms_code", "")
        matches, price_history, tx_history = [], [], []

        if bqms:
            rows = await conn.fetch(
                "SELECT bqms_code,product_name,spec,maker,type,unit FROM products WHERE bqms_code=$1 LIMIT 1", bqms)
            matches.extend([dict(r) for r in rows])
        if not matches and spec:
            rows = await conn.fetch(
                "SELECT bqms_code,product_name,spec,maker,type,unit FROM products WHERE spec ILIKE $1 OR product_name ILIKE $1 LIMIT 5",
                f"%{spec[:50]}%")
            matches.extend([dict(r) for r in rows])
        if bqms:
            rows = await conn.fetch(
                "SELECT rfq_no,price_bqms_v1,price_bqms_v2,price_bqms_v3,price_bqms_v4,supplier,result,date FROM quotations WHERE bqms_code=$1 ORDER BY date DESC LIMIT 10", bqms)
            price_history = [dict(r) for r in rows]
            rows = await conn.fetch(
                "SELECT rfq_no,unit_price_usd,unit_price_vnd,buyer,seller,transaction_date,quantity FROM transactions WHERE bqms_code=$1 AND unit_price_usd IS NOT NULL ORDER BY transaction_date DESC LIMIT 5", bqms)
            tx_history = [dict(r) for r in rows]

        results.append({"input": item, "product_matches": matches, "price_history": price_history,
                         "transaction_history": tx_history, "match_count": len(matches), "has_price": len(price_history) > 0 or len(tx_history) > 0})

    matched = sum(1 for r in results if r["match_count"] > 0)
    return {"results": results, "summary": {"total": len(results), "matched": matched, "with_price": sum(1 for r in results if r["has_price"]), "unmatched": len(results) - matched}}


# ── Tool 3: AI Classification ──────────────────────────

@router.post("/classify")
async def classify_orders(
    items: list[dict], conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    results = []
    for item in items[:100]:
        bqms = item.get("bqms_code", "")
        history = await conn.fetch("SELECT result, COUNT(*) as cnt FROM quotations WHERE bqms_code=$1 AND result IS NOT NULL GROUP BY result", bqms)
        history_map = {r["result"]: r["cnt"] for r in history}
        wins = history_map.get("Y", 0) + history_map.get("y", 0)
        losses = history_map.get("N", 0) + history_map.get("n", 0)
        has_price = await conn.fetchval("SELECT COUNT(*) FROM quotations WHERE bqms_code=$1 AND (price_bqms_v1 IS NOT NULL OR price_bqms_v2 IS NOT NULL)", bqms) or 0

        if wins > 0 and has_price > 0:
            decision, confidence, reason = "yes", min(0.9, 0.5 + wins * 0.1), f"Da thang {wins} lan, co du lieu gia"
        elif wins > 0:
            decision, confidence, reason = "maybe", 0.5, f"Da thang {wins} lan nhung chua co gia gan day"
        elif losses > 2:
            decision, confidence, reason = "no", 0.7, f"Da thua {losses} lan, kha nang thap"
        elif has_price > 0:
            decision, confidence, reason = "maybe", 0.4, "Co du lieu gia nhung chua co lich su thang"
        else:
            decision, confidence, reason = "maybe", 0.3, "Khong co lich su — can xem xet thu cong"

        results.append({"input": item, "decision": decision, "confidence": confidence, "reason": reason, "history": {"wins": wins, "losses": losses, "has_price": has_price}})

    return {"results": results, "summary": {"total": len(results), "yes": sum(1 for r in results if r["decision"] == "yes"),
            "no": sum(1 for r in results if r["decision"] == "no"), "maybe": sum(1 for r in results if r["decision"] == "maybe")}}


# ── Tool 5: Market Prices ──────────────────────────────

@router.get("/market-prices")
async def list_market_prices(bqms_code: str = "", platform: str = "", page: int = 1, limit: int = 50, conn=Depends(get_db), _=Depends(get_current_user)):
    conditions, params, idx = [], [], 1
    if bqms_code: conditions.append(f"bqms_code=${idx}"); params.append(bqms_code); idx += 1
    if platform: conditions.append(f"platform=${idx}"); params.append(platform); idx += 1
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * min(limit, 100)
    total = await conn.fetchval(f"SELECT COUNT(*) FROM market_prices {where}", *params)
    rows = await conn.fetch(f"SELECT * FROM market_prices {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}", *params, min(limit, 100), offset)
    return {"data": [dict(r) for r in rows], "total": total, "page": page}

@router.post("/market-prices")
async def save_market_price(body: dict, conn=Depends(get_db), user=Depends(require_role(UserRole.admin, UserRole.procurement))):
    row = await conn.fetchrow(
        "INSERT INTO market_prices (bqms_code,product_name,spec,maker,platform,supplier_name,supplier_url,price,currency,price_usd,moq,match_confidence,confirmed,confirmed_by,confirmed_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,TRUE,$13,NOW()) RETURNING id",
        body.get("bqms_code"), body.get("product_name",""), body.get("spec"), body.get("maker"), body.get("platform"), body.get("supplier_name"), body.get("supplier_url"),
        body.get("price"), body.get("currency","USD"), body.get("price_usd"), body.get("moq"), body.get("match_confidence"), user["id"])
    return {"success": True, "id": row["id"]}

@router.delete("/market-prices/{price_id}")
async def delete_market_price(price_id: int, conn=Depends(get_db), _=Depends(require_role(UserRole.admin))):
    result = await conn.execute("DELETE FROM market_prices WHERE id=$1", price_id)
    if result != "DELETE 1": raise NotFoundError("MarketPrice", str(price_id))
    return {"success": True}


# ── Tool 4: Push deliveries ────────────────────────────

@router.post("/push-deliveries")
async def push_deliveries(deliveries: list[dict], conn=Depends(get_db), _=Depends(require_role(UserRole.admin, UserRole.procurement))):
    inserted = 0
    for d in deliveries[:500]:
        try:
            await conn.execute(
                "INSERT INTO po_deliveries (po_date,po_number,shipping_no,rfq_no,bqms_code,spec,quantity,unit,unit_price,total_amount,buyer,receiver_name,status,delivery_date,actual_qty,source_file,row_hash) VALUES ($1::date,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14::date,$15,$16,$17) ON CONFLICT (row_hash) DO NOTHING",
                d.get("po_date"), d.get("po_number"), d.get("shipping_no"), d.get("rfq_no"), d.get("bqms_code"), d.get("spec"),
                d.get("quantity"), d.get("unit"), d.get("unit_price"), d.get("total_amount"), d.get("buyer"), d.get("receiver_name"),
                d.get("status"), d.get("delivery_date"), d.get("actual_qty"), d.get("source_file","desktop_push"), d.get("row_hash",""))
            inserted += 1
        except Exception: continue
    return {"success": True, "inserted": inserted, "total": len(deliveries)}


# ── Dashboard KPIs (comprehensive) ─────────────────────

@router.get("/dashboard")
async def dashboard_kpis(conn=Depends(get_db), _=Depends(get_current_user)):
    kpis = {}

    # Transaction overview
    row = await conn.fetchrow("""
        SELECT COUNT(*) as total, COUNT(DISTINCT rfq_no) as unique_rfq, COUNT(DISTINCT bqms_code) as unique_bqms,
               COUNT(CASE WHEN type='gc' THEN 1 END) as gc_count, COUNT(CASE WHEN type='tm' THEN 1 END) as tm_count,
               COALESCE(SUM(price_quoted),0) as total_usd
        FROM transactions""")
    kpis["transactions"] = dict(row)

    # Quotation win/loss
    row = await conn.fetchrow("""
        SELECT COUNT(*) as total, COUNT(CASE WHEN result IN ('Y','y') THEN 1 END) as wins,
               COUNT(CASE WHEN result IN ('N','n') THEN 1 END) as losses
        FROM quotations""")
    kpis["quotations"] = dict(row)
    total_q = row["wins"] + row["losses"]
    kpis["quotations"]["win_rate"] = round(row["wins"] / total_q * 100, 1) if total_q > 0 else 0

    # GC vs TM pie chart data
    kpis["type_split"] = {"gc": kpis["transactions"]["gc_count"], "tm": kpis["transactions"]["tm_count"],
                          "other": kpis["transactions"]["total"] - kpis["transactions"]["gc_count"] - kpis["transactions"]["tm_count"]}

    # Monthly trend (last 6 months)
    rows = await conn.fetch("""
        SELECT TO_CHAR(date, 'YYYY-MM') as month, COUNT(*) as total,
               COUNT(CASE WHEN result IN ('Y','y') THEN 1 END) as wins,
               COUNT(CASE WHEN result IN ('N','n') THEN 1 END) as losses
        FROM quotations WHERE date >= CURRENT_DATE - INTERVAL '6 months' AND date IS NOT NULL
        GROUP BY TO_CHAR(date, 'YYYY-MM') ORDER BY month""")
    kpis["monthly_trend"] = [dict(r) for r in rows]

    # Win rate by supplier (top 10)
    rows = await conn.fetch("""
        SELECT supplier, COUNT(*) as total, COUNT(CASE WHEN result IN ('Y','y') THEN 1 END) as wins,
               ROUND(COUNT(CASE WHEN result IN ('Y','y') THEN 1 END)::numeric / NULLIF(COUNT(*),0) * 100, 1) as win_pct
        FROM quotations WHERE supplier IS NOT NULL AND supplier != ''
        GROUP BY supplier HAVING COUNT(*) >= 3 ORDER BY win_pct DESC, total DESC LIMIT 10""")
    kpis["supplier_ranking"] = [dict(r) for r in rows]

    # Top makers
    rows = await conn.fetch("""
        SELECT maker, COUNT(*) as cnt FROM products WHERE maker IS NOT NULL AND maker != ''
        GROUP BY maker ORDER BY cnt DESC LIMIT 8""")
    kpis["top_makers"] = [dict(r) for r in rows]

    # Delivery stats
    row = await conn.fetchrow("""
        SELECT COUNT(*) as total, SUM(total_amount) as total_value,
               COUNT(CASE WHEN delivery_date IS NOT NULL THEN 1 END) as delivered,
               COUNT(CASE WHEN delivery_date IS NULL AND status IS NOT NULL THEN 1 END) as pending
        FROM po_deliveries""")
    kpis["deliveries"] = dict(row)

    # Recent transactions (newest first)
    rows = await conn.fetch("""
        SELECT rfq_no, bqms_code, spec, type, maker, transaction_date, unit_price_usd
        FROM transactions WHERE transaction_date IS NOT NULL
        ORDER BY transaction_date DESC LIMIT 8""")
    kpis["recent"] = [dict(r) for r in rows]

    # Alerts
    alerts = []
    # Expired quotes
    expired = await conn.fetchval("SELECT COUNT(*) FROM quotations WHERE result IS NULL AND date < CURRENT_DATE - INTERVAL '30 days'")
    if expired and expired > 0:
        alerts.append({"level": "warning", "message": f"{expired} bao gia qua 30 ngay chua co ket qua"})
    # Products without price
    no_price = await conn.fetchval("SELECT COUNT(*) FROM products WHERE current_stock = 0")
    if no_price and no_price > 100:
        alerts.append({"level": "info", "message": f"{no_price:,} san pham chua cap nhat ton kho"})
    # Pending deliveries
    pending_dlv = await conn.fetchval("SELECT COUNT(*) FROM po_deliveries WHERE delivery_date IS NULL")
    if pending_dlv and pending_dlv > 0:
        alerts.append({"level": "warning", "message": f"{pending_dlv} don giao hang dang cho xu ly"})
    kpis["alerts"] = alerts

    return kpis


# ── Platform Profiles ───────────────────────────────────

@router.get("/platform-profiles")
async def list_profiles(conn=Depends(get_db), _=Depends(require_role(UserRole.admin))):
    rows = await conn.fetch("SELECT id,platform,username,notes,created_at FROM platform_profiles ORDER BY platform")
    return {"data": [dict(r) for r in rows]}

@router.post("/platform-profiles")
async def save_profile(body: dict, conn=Depends(get_db), _=Depends(require_role(UserRole.admin))):
    row = await conn.fetchrow(
        "INSERT INTO platform_profiles (platform,username,password_enc,notes) VALUES ($1,$2,$3,$4) ON CONFLICT (platform,username) DO UPDATE SET password_enc=EXCLUDED.password_enc,notes=EXCLUDED.notes RETURNING id",
        body["platform"], body["username"], body.get("password",""), body.get("notes"))
    return {"success": True, "id": row["id"]}
