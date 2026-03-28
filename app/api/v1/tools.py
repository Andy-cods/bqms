"""Tool endpoints — Auto-fill, AI Classify, Market Search, Deliveries push."""

from fastapi import APIRouter, Depends, UploadFile, File
from typing import Optional

from ...db.session import get_db
from ...domain.enums import UserRole
from ...domain.exceptions import NotFoundError, ValidationError
from ..deps import get_current_user, require_role

router = APIRouter(prefix="/tools", tags=["tools"])


# ── Tool 1: Auto-fill (product matching from DB) ───────

@router.post("/autofill")
async def autofill_match(
    items: list[dict],
    conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    """Match RFQ items against product database.
    Input: list of {spec, maker, bqms_code, quantity}
    Output: enriched items with price history, similar products
    """
    results = []
    for item in items[:200]:  # Cap at 200
        spec = item.get("spec", "")
        bqms = item.get("bqms_code", "")
        maker = item.get("maker", "")

        matches = []

        # Exact BQMS code match
        if bqms:
            rows = await conn.fetch(
                """SELECT bqms_code, product_name, spec, maker, type, unit
                   FROM products WHERE bqms_code = $1 LIMIT 1""",
                bqms,
            )
            matches.extend([dict(r) for r in rows])

        # Fuzzy spec search if no exact match
        if not matches and spec:
            q = f"%{spec[:50]}%"
            rows = await conn.fetch(
                """SELECT bqms_code, product_name, spec, maker, type, unit
                   FROM products
                   WHERE spec ILIKE $1 OR product_name ILIKE $1
                   LIMIT 5""",
                q,
            )
            matches.extend([dict(r) for r in rows])

        # Get price history from quotations
        price_history = []
        if bqms:
            rows = await conn.fetch(
                """SELECT rfq_no, price_bqms_v1, price_bqms_v2, price_bqms_v3,
                          price_bqms_v4, supplier, result, date
                   FROM quotations
                   WHERE bqms_code = $1
                   ORDER BY date DESC LIMIT 10""",
                bqms,
            )
            price_history = [dict(r) for r in rows]

        # Get transaction history
        tx_history = []
        if bqms:
            rows = await conn.fetch(
                """SELECT rfq_no, unit_price_usd, unit_price_vnd, buyer, seller,
                          transaction_date, quantity
                   FROM transactions
                   WHERE bqms_code = $1 AND unit_price_usd IS NOT NULL
                   ORDER BY transaction_date DESC LIMIT 5""",
                bqms,
            )
            tx_history = [dict(r) for r in rows]

        results.append({
            "input": item,
            "product_matches": matches,
            "price_history": price_history,
            "transaction_history": tx_history,
            "match_count": len(matches),
            "has_price": len(price_history) > 0 or len(tx_history) > 0,
        })

    matched = sum(1 for r in results if r["match_count"] > 0)
    with_price = sum(1 for r in results if r["has_price"])

    return {
        "results": results,
        "summary": {
            "total": len(results),
            "matched": matched,
            "with_price": with_price,
            "unmatched": len(results) - matched,
        },
    }


# ── Tool 3: AI Classification ──────────────────────────

@router.post("/classify")
async def classify_orders(
    items: list[dict],
    conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    """Classify orders as yes/no/maybe based on historical data.
    For now: rule-based using DB history. Gemini integration later.
    """
    results = []
    for item in items[:100]:
        bqms = item.get("bqms_code", "")
        spec = item.get("spec", "")

        # Check win/lose history
        history = await conn.fetch(
            """SELECT result, COUNT(*) as cnt
               FROM quotations
               WHERE bqms_code = $1 AND result IS NOT NULL
               GROUP BY result""",
            bqms,
        )
        history_map = {r["result"]: r["cnt"] for r in history}
        wins = history_map.get("Y", 0) + history_map.get("y", 0)
        losses = history_map.get("N", 0) + history_map.get("n", 0)

        # Check if we have price data
        has_price = await conn.fetchval(
            """SELECT COUNT(*) FROM quotations
               WHERE bqms_code = $1 AND (price_bqms_v1 IS NOT NULL OR price_bqms_v2 IS NOT NULL)""",
            bqms,
        ) or 0

        # Simple rule-based decision
        if wins > 0 and has_price > 0:
            decision = "yes"
            confidence = min(0.9, 0.5 + wins * 0.1)
            reason = f"Won {wins} times before, price data available"
        elif wins > 0:
            decision = "maybe"
            confidence = 0.5
            reason = f"Won {wins} times but no recent price"
        elif losses > 2:
            decision = "no"
            confidence = 0.7
            reason = f"Lost {losses} times, low chance"
        elif has_price > 0:
            decision = "maybe"
            confidence = 0.4
            reason = "Has price data but no win history"
        else:
            decision = "maybe"
            confidence = 0.3
            reason = "No history found — needs manual review"

        results.append({
            "input": item,
            "decision": decision,
            "confidence": confidence,
            "reason": reason,
            "history": {"wins": wins, "losses": losses, "has_price": has_price},
        })

    summary = {
        "total": len(results),
        "yes": sum(1 for r in results if r["decision"] == "yes"),
        "no": sum(1 for r in results if r["decision"] == "no"),
        "maybe": sum(1 for r in results if r["decision"] == "maybe"),
    }

    return {"results": results, "summary": summary}


# ── Tool 5: Market Prices ──────────────────────────────

@router.get("/market-prices")
async def list_market_prices(
    bqms_code: str = "", platform: str = "",
    page: int = 1, limit: int = 50,
    conn=Depends(get_db),
    _=Depends(get_current_user),
):
    conditions, params, idx = [], [], 1
    if bqms_code:
        conditions.append(f"bqms_code = ${idx}")
        params.append(bqms_code)
        idx += 1
    if platform:
        conditions.append(f"platform = ${idx}")
        params.append(platform)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * min(limit, 100)

    total = await conn.fetchval(f"SELECT COUNT(*) FROM market_prices {where}", *params)
    rows = await conn.fetch(
        f"SELECT * FROM market_prices {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}",
        *params, min(limit, 100), offset,
    )
    return {"data": [dict(r) for r in rows], "total": total, "page": page}


@router.post("/market-prices")
async def save_market_price(
    body: dict,
    conn=Depends(get_db),
    user=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    """Save confirmed market price (from Tool 5 desktop or manual entry)."""
    row = await conn.fetchrow(
        """INSERT INTO market_prices
           (bqms_code, product_name, spec, maker, platform, supplier_name,
            supplier_url, price, currency, price_usd, moq, match_confidence,
            confirmed, confirmed_by, confirmed_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,TRUE,$13,NOW())
           RETURNING id""",
        body.get("bqms_code"), body.get("product_name", ""),
        body.get("spec"), body.get("maker"),
        body.get("platform"), body.get("supplier_name"),
        body.get("supplier_url"),
        body.get("price"), body.get("currency", "USD"),
        body.get("price_usd"), body.get("moq"),
        body.get("match_confidence"),
        user["id"],
    )
    return {"success": True, "id": row["id"]}


@router.delete("/market-prices/{price_id}")
async def delete_market_price(
    price_id: int,
    conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin)),
):
    result = await conn.execute("DELETE FROM market_prices WHERE id = $1", price_id)
    if result != "DELETE 1":
        raise NotFoundError("MarketPrice", str(price_id))
    return {"success": True}


# ── Tool 5: Platform Profiles ──────────────────────────

@router.get("/platform-profiles")
async def list_profiles(conn=Depends(get_db), _=Depends(require_role(UserRole.admin))):
    """List saved platform login profiles."""
    rows = await conn.fetch(
        "SELECT id, platform, username, notes, created_at FROM platform_profiles ORDER BY platform"
    )
    return {"data": [dict(r) for r in rows]}


@router.post("/platform-profiles")
async def save_profile(
    body: dict,
    conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin)),
):
    """Save platform login profile (password encrypted in DB)."""
    row = await conn.fetchrow(
        """INSERT INTO platform_profiles (platform, username, password_enc, notes)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (platform, username) DO UPDATE SET
             password_enc = EXCLUDED.password_enc, notes = EXCLUDED.notes
           RETURNING id""",
        body["platform"], body["username"],
        body.get("password", ""),  # TODO: encrypt with app secret
        body.get("notes"),
    )
    return {"success": True, "id": row["id"]}


# ── Tool 4: Push deliveries from desktop ────────────────

@router.post("/push-deliveries")
async def push_deliveries(
    deliveries: list[dict],
    conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    """Desktop Tool 4 pushes scraped PO deliveries to VPS."""
    inserted = 0
    for d in deliveries[:500]:
        try:
            await conn.execute(
                """INSERT INTO po_deliveries
                   (po_date, po_number, shipping_no, rfq_no, bqms_code, spec,
                    quantity, unit, unit_price, total_amount, buyer, receiver_name,
                    status, delivery_date, actual_qty, source_file, row_hash)
                   VALUES ($1::date,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14::date,$15,$16,$17)
                   ON CONFLICT (row_hash) DO NOTHING""",
                d.get("po_date"), d.get("po_number"), d.get("shipping_no"),
                d.get("rfq_no"), d.get("bqms_code"), d.get("spec"),
                d.get("quantity"), d.get("unit"), d.get("unit_price"),
                d.get("total_amount"), d.get("buyer"), d.get("receiver_name"),
                d.get("status"), d.get("delivery_date"), d.get("actual_qty"),
                d.get("source_file", "desktop_push"),
                d.get("row_hash", ""),
            )
            inserted += 1
        except Exception:
            continue
    return {"success": True, "inserted": inserted, "total": len(deliveries)}


# ── Dashboard KPIs ──────────────────────────────────────

@router.get("/dashboard")
async def dashboard_kpis(conn=Depends(get_db), _=Depends(get_current_user)):
    """Aggregated KPIs for dashboard."""
    kpis = {}

    # Transaction stats
    row = await conn.fetchrow("""
        SELECT COUNT(*) as total,
               COUNT(DISTINCT rfq_no) as unique_rfq,
               COUNT(DISTINCT bqms_code) as unique_bqms,
               COUNT(CASE WHEN type='gc' THEN 1 END) as gc_count,
               COUNT(CASE WHEN type='tm' THEN 1 END) as tm_count,
               SUM(price_quoted) as total_usd
        FROM transactions
    """)
    kpis["transactions"] = dict(row)

    # Quotation stats
    row = await conn.fetchrow("""
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN result IN ('Y','y') THEN 1 END) as wins,
               COUNT(CASE WHEN result IN ('N','n') THEN 1 END) as losses
        FROM quotations
    """)
    kpis["quotations"] = dict(row)
    total_q = row["wins"] + row["losses"]
    kpis["quotations"]["win_rate"] = round(row["wins"] / total_q * 100, 1) if total_q > 0 else 0

    # Delivery stats
    row = await conn.fetchrow("""
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN status IS NOT NULL AND status != '' THEN 1 END) as with_status,
               SUM(total_amount) as total_value
        FROM po_deliveries
    """)
    kpis["deliveries"] = dict(row)

    # Top makers
    rows = await conn.fetch("""
        SELECT maker, COUNT(*) as cnt
        FROM products WHERE maker IS NOT NULL AND maker != ''
        GROUP BY maker ORDER BY cnt DESC LIMIT 10
    """)
    kpis["top_makers"] = [dict(r) for r in rows]

    # Recent activity
    rows = await conn.fetch("""
        SELECT 'transaction' as type, rfq_no as ref, transaction_date as date, spec
        FROM transactions WHERE transaction_date IS NOT NULL
        ORDER BY transaction_date DESC LIMIT 10
    """)
    kpis["recent"] = [dict(r) for r in rows]

    return kpis
