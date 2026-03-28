"""Tool engines — redesigned for PostgreSQL backend.

Tool 1: Nhận RFQ mới → match sản phẩm từ DB → trả giá lịch sử + đề xuất
Tool 2: Dashboard analytics từ quotations/transactions/deliveries tables
Tool 3: Phân loại đơn hàng dựa trên lịch sử thắng/thua trong DB
Tool 5: Tìm kiếm giá từ DB nội bộ + lịch sử giao dịch thực tế
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks

from ...db.session import get_db
from ...domain.enums import UserRole
from ...domain.exceptions import NotFoundError, ValidationError
from ..deps import get_current_user, require_role

router = APIRouter(prefix="/tool-engine", tags=["tool-engines"])


async def _get_conn():
    """Get a fresh connection for background tasks (not from request scope)."""
    from ...db.session import pool, create_pool
    p = pool
    if p is None:
        p = await create_pool()
    return await p.acquire()

_jobs: dict[str, dict] = {}


def _new_job(job_type: str) -> str:
    jid = uuid.uuid4().hex[:12]
    _jobs[jid] = {"status": "running", "type": job_type, "progress": 0,
                  "logs": [], "result": None, "error": None, "started_at": datetime.now().isoformat()}
    return jid


def _log(jid: str, msg: str):
    if jid in _jobs:
        _jobs[jid]["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ═══════════════════════════════════════════════════════
# TOOL 1: TỰ ĐỘNG ĐIỀN BÁO GIÁ
# Input: danh sách BQMS codes (từ form hoặc upload Excel)
# Output: mỗi sản phẩm → thông tin chi tiết + giá lịch sử + NCC đề xuất
# ═══════════════════════════════════════════════════════

@router.post("/tool1/lookup")
async def tool1_lookup(
    body: dict,
    conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    """Tra cứu nhanh: nhập BQMS codes → trả kết quả ngay."""
    codes = body.get("codes", [])  # list of bqms_code strings
    if not codes:
        raise ValidationError("Cần ít nhất 1 mã BQMS")

    results = []
    for code in codes[:100]:
        code = str(code).strip()
        if not code:
            continue

        # 1. Tìm sản phẩm trong DB
        product = await conn.fetchrow(
            "SELECT * FROM products WHERE bqms_code = $1", code)

        # 2. Lịch sử báo giá (giá V1→V4, NCC, kết quả thắng/thua)
        quotes = await conn.fetch("""
            SELECT date, rfq_no, price_bqms_v1, price_bqms_v2, price_bqms_v3,
                   price_bqms_v4, supplier, result, person_in_charge
            FROM quotations WHERE bqms_code = $1
            ORDER BY date DESC LIMIT 10""", code)

        # 3. Giá mua thực tế (từ transactions — đã nhập khẩu)
        actual = await conn.fetch("""
            SELECT transaction_date, unit_price_usd, unit_price_vnd,
                   seller, buyer, quantity, rfq_no
            FROM transactions
            WHERE bqms_code = $1 AND unit_price_usd IS NOT NULL
            ORDER BY transaction_date DESC LIMIT 5""", code)

        # 4. Giá thị trường (từ Tool 5 saved)
        market = await conn.fetch("""
            SELECT platform, supplier_name, price_usd, moq, created_at
            FROM market_prices WHERE bqms_code = $1
            ORDER BY created_at DESC LIMIT 5""", code)

        # 5. Tính giá đề xuất
        prices_usd = [r["unit_price_usd"] for r in actual if r["unit_price_usd"]]
        avg_price = sum(prices_usd) / len(prices_usd) if prices_usd else None
        min_price = min(prices_usd) if prices_usd else None
        max_price = max(prices_usd) if prices_usd else None

        # 6. NCC tốt nhất (thắng nhiều nhất)
        best_suppliers = await conn.fetch("""
            SELECT supplier, COUNT(*) as total,
                   COUNT(CASE WHEN result IN ('Y','y') THEN 1 END) as wins
            FROM quotations WHERE bqms_code = $1 AND supplier IS NOT NULL
            GROUP BY supplier ORDER BY wins DESC LIMIT 3""", code)

        results.append({
            "bqms_code": code,
            "product": dict(product) if product else None,
            "quote_history": [dict(r) for r in quotes],
            "actual_prices": [dict(r) for r in actual],
            "market_prices": [dict(r) for r in market],
            "price_summary": {
                "avg_usd": round(avg_price, 4) if avg_price else None,
                "min_usd": round(min_price, 4) if min_price else None,
                "max_usd": round(max_price, 4) if max_price else None,
                "data_points": len(prices_usd),
            },
            "best_suppliers": [dict(r) for r in best_suppliers],
            "found": product is not None,
        })

    return {
        "results": results,
        "summary": {
            "total": len(results),
            "found": sum(1 for r in results if r["found"]),
            "with_price": sum(1 for r in results if r["price_summary"]["data_points"] > 0),
            "not_found": sum(1 for r in results if not r["found"]),
        },
    }


@router.post("/tool1/upload")
async def tool1_upload_excel(
    file: UploadFile = File(...),
    conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    """Upload Excel BC BQMS → parse → trả danh sách đơn hàng."""
    import os, openpyxl
    if not file.filename or not file.filename.endswith((".xlsx", ".xls", ".xlsm")):
        raise ValidationError("Chỉ chấp nhận file Excel")

    os.makedirs("/opt/songchau/data/uploads", exist_ok=True)
    tmp = f"/opt/songchau/data/uploads/t1_{uuid.uuid4().hex[:8]}_{file.filename}"
    content = await file.read()
    with open(tmp, "wb") as f:
        f.write(content)

    wb = openpyxl.load_workbook(tmp, read_only=True, data_only=True)
    orders = []
    for sname in wb.sheetnames:
        ws = wb[sname]
        headers = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                headers = [str(c or "").strip().lower() for c in row]
                continue
            if not row or not any(v for v in row[:6] if v):
                continue
            order = {}
            for j, h in enumerate(headers):
                if j < len(row) and row[j] is not None:
                    val = row[j]
                    # Map Vietnamese column names
                    if any(k in h for k in ["bqms", "bmsq", "mã"]):
                        order["bqms_code"] = str(val).strip()
                    elif any(k in h for k in ["đơn hàng", "don hang", "rfq", "quotation"]):
                        order["rfq_no"] = str(val).strip()
                    elif any(k in h for k in ["tên hàng", "ten hang", "spec", "mô tả"]):
                        order["spec"] = str(val).strip()
                    elif any(k in h for k in ["maker", "hãng", "hang"]):
                        order["maker"] = str(val).strip()
                    elif any(k in h for k in ["loại", "loai", "type"]):
                        order["type"] = str(val).strip()
                    elif any(k in h for k in ["số lượng", "so luong", "qty", "sl"]):
                        try:
                            order["quantity"] = float(val)
                        except (ValueError, TypeError):
                            pass
                    elif any(k in h for k in ["hạn", "han", "deadline"]):
                        order["deadline"] = str(val).strip()
            if order.get("bqms_code") or order.get("rfq_no") or order.get("spec"):
                orders.append(order)
        break  # Only first sheet

    wb.close()
    return {"success": True, "file": file.filename, "orders": orders[:300], "count": len(orders)}


# ═══════════════════════════════════════════════════════
# TOOL 2: THỐNG KÊ & PHÂN TÍCH GIÁ
# Tất cả data đã ở PostgreSQL — chỉ cần query
# ═══════════════════════════════════════════════════════

@router.get("/tool2/overview")
async def tool2_overview(conn=Depends(get_db), _=Depends(get_current_user)):
    """Tổng quan thống kê: KPIs + phân tích."""

    # KPIs
    q_stats = await conn.fetchrow("""
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN result IN ('Y','y') THEN 1 END) as wins,
               COUNT(CASE WHEN result IN ('N','n') THEN 1 END) as losses,
               COUNT(DISTINCT supplier) as unique_ncc,
               AVG(price_bqms_v1) as avg_v1
        FROM quotations WHERE result IS NOT NULL""")

    tx_stats = await conn.fetchrow("""
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN type='gc' THEN 1 END) as gc,
               COUNT(CASE WHEN type='tm' THEN 1 END) as tm,
               COALESCE(SUM(price_quoted), 0) as total_usd,
               COUNT(DISTINCT rfq_no) as unique_rfq,
               COUNT(DISTINCT maker) as unique_maker
        FROM transactions""")

    dlv_stats = await conn.fetchrow("""
        SELECT COUNT(*) as total,
               COALESCE(SUM(total_amount), 0) as total_value,
               COUNT(CASE WHEN delivery_date IS NOT NULL THEN 1 END) as delivered
        FROM po_deliveries""")

    # Xu hướng theo tháng (12 tháng gần nhất)
    monthly = await conn.fetch("""
        SELECT TO_CHAR(date, 'YYYY-MM') as month,
               COUNT(*) as total,
               COUNT(CASE WHEN result IN ('Y','y') THEN 1 END) as wins,
               COUNT(CASE WHEN result IN ('N','n') THEN 1 END) as losses
        FROM quotations
        WHERE date >= CURRENT_DATE - INTERVAL '12 months' AND date IS NOT NULL
        GROUP BY TO_CHAR(date, 'YYYY-MM') ORDER BY month""")

    # Top NCC theo tỷ lệ thắng
    top_ncc = await conn.fetch("""
        SELECT supplier, COUNT(*) as total,
               COUNT(CASE WHEN result IN ('Y','y') THEN 1 END) as wins,
               ROUND(COUNT(CASE WHEN result IN ('Y','y') THEN 1 END)::numeric
                     / NULLIF(COUNT(*), 0) * 100, 1) as win_pct
        FROM quotations
        WHERE supplier IS NOT NULL AND supplier != '' AND result IS NOT NULL
        GROUP BY supplier HAVING COUNT(*) >= 3
        ORDER BY win_pct DESC LIMIT 10""")

    # Top makers theo số lượng sản phẩm
    top_makers = await conn.fetch("""
        SELECT maker, COUNT(*) as cnt,
               COUNT(CASE WHEN type='gc' THEN 1 END) as gc,
               COUNT(CASE WHEN type='tm' THEN 1 END) as tm
        FROM products WHERE maker IS NOT NULL AND maker != ''
        GROUP BY maker ORDER BY cnt DESC LIMIT 10""")

    # Phân bố giá theo loại (GC vs TM)
    price_dist = await conn.fetch("""
        SELECT type, COUNT(*) as cnt,
               AVG(unit_price_usd) as avg_usd,
               MIN(unit_price_usd) as min_usd,
               MAX(unit_price_usd) as max_usd
        FROM transactions
        WHERE type IS NOT NULL AND unit_price_usd IS NOT NULL
        GROUP BY type""")

    # Buyer analysis
    buyers = await conn.fetch("""
        SELECT buyer, COUNT(*) as cnt,
               COALESCE(SUM(total_amount), 0) as total_value
        FROM po_deliveries WHERE buyer IS NOT NULL
        GROUP BY buyer ORDER BY cnt DESC""")

    total_q = (q_stats["wins"] or 0) + (q_stats["losses"] or 0)
    return {
        "quotations": {**dict(q_stats), "win_rate": round((q_stats["wins"] or 0) / total_q * 100, 1) if total_q > 0 else 0},
        "transactions": dict(tx_stats),
        "deliveries": dict(dlv_stats),
        "monthly_trend": [dict(r) for r in monthly],
        "top_suppliers": [dict(r) for r in top_ncc],
        "top_makers": [dict(r) for r in top_makers],
        "price_distribution": [dict(r) for r in price_dist],
        "buyers": [dict(r) for r in buyers],
    }


@router.get("/tool2/quotations")
async def tool2_quotations(
    q: str = "", result: str = "", person: str = "",
    page: int = 1, limit: int = 25,
    conn=Depends(get_db), _=Depends(get_current_user),
):
    """Danh sách báo giá chi tiết với filter."""
    conditions, params, idx = [], [], 1
    if q:
        conditions.append(f"(rfq_no ILIKE ${idx} OR bqms_code ILIKE ${idx} OR spec ILIKE ${idx} OR supplier ILIKE ${idx})")
        params.append(f"%{q}%"); idx += 1
    if result:
        conditions.append(f"result = ${idx}")
        params.append(result); idx += 1
    if person:
        conditions.append(f"person_in_charge ILIKE ${idx}")
        params.append(f"%{person}%"); idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * min(limit, 100)
    total = await conn.fetchval(f"SELECT COUNT(*) FROM quotations {where}", *params)
    rows = await conn.fetch(
        f"SELECT * FROM quotations {where} ORDER BY date DESC NULLS LAST LIMIT ${idx} OFFSET ${idx+1}",
        *params, min(limit, 100), offset)
    return {"data": [dict(r) for r in rows], "total": total, "page": page, "pages": (total + min(limit, 100) - 1) // min(limit, 100)}


@router.get("/tool2/deliveries")
async def tool2_deliveries(
    q: str = "", page: int = 1, limit: int = 25,
    conn=Depends(get_db), _=Depends(get_current_user),
):
    """Danh sách giao hàng."""
    offset = (page - 1) * min(limit, 100)
    if q:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM po_deliveries WHERE po_number ILIKE $1 OR bqms_code ILIKE $1 OR spec ILIKE $1", f"%{q}%")
        rows = await conn.fetch(
            "SELECT * FROM po_deliveries WHERE po_number ILIKE $1 OR bqms_code ILIKE $1 OR spec ILIKE $1 ORDER BY po_date DESC NULLS LAST LIMIT $2 OFFSET $3",
            f"%{q}%", min(limit, 100), offset)
    else:
        total = await conn.fetchval("SELECT COUNT(*) FROM po_deliveries")
        rows = await conn.fetch(
            "SELECT * FROM po_deliveries ORDER BY po_date DESC NULLS LAST LIMIT $1 OFFSET $2", min(limit, 100), offset)
    return {"data": [dict(r) for r in rows], "total": total, "page": page, "pages": (total + min(limit, 100) - 1) // min(limit, 100)}


# ═══════════════════════════════════════════════════════
# TOOL 3: PHÂN LOẠI AI
# Dùng lịch sử thắng/thua + sản phẩm tương tự trong DB
# ═══════════════════════════════════════════════════════

@router.post("/tool3/classify")
async def tool3_classify(
    body: dict,
    background_tasks: BackgroundTasks,
    conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    """Phân loại đơn hàng: Tham gia / Bỏ qua / Xem xét."""
    job_id = _new_job("classify")
    orders = body.get("orders", [])

    async def _run():
        conn = await _get_conn()
        try:
            results = []
            for i, order in enumerate(orders):
                bqms = order.get("bqms_code", "")
                spec = order.get("spec", "")
                maker = order.get("maker", "")

                # 1. Lịch sử trực tiếp
                hist = await conn.fetch(
                    "SELECT result, COUNT(*) as cnt FROM quotations WHERE bqms_code=$1 AND result IS NOT NULL GROUP BY result", bqms)
                wins = sum(r["cnt"] for r in hist if r["result"] in ("Y", "y"))
                losses = sum(r["cnt"] for r in hist if r["result"] in ("N", "n"))

                # 2. Có giá không?
                has_price = await conn.fetchval(
                    "SELECT COUNT(*) FROM quotations WHERE bqms_code=$1 AND price_bqms_v1 IS NOT NULL", bqms) or 0

                # 3. Giá mua thực tế?
                actual_price = await conn.fetchval(
                    "SELECT AVG(unit_price_usd) FROM transactions WHERE bqms_code=$1 AND unit_price_usd IS NOT NULL", bqms)

                # 4. Sản phẩm tương tự (cùng maker, spec gần giống)
                similar_wins = 0
                similar_total = 0
                if maker:
                    sim = await conn.fetchrow(
                        """SELECT COUNT(*) as total,
                                  COUNT(CASE WHEN result IN ('Y','y') THEN 1 END) as wins
                           FROM quotations WHERE maker ILIKE $1 AND result IS NOT NULL""",
                        f"%{maker}%")
                    similar_wins = sim["wins"] or 0
                    similar_total = sim["total"] or 0

                # 5. Quyết định
                if wins >= 2 and has_price > 0:
                    decision, confidence = "yes", min(0.95, 0.6 + wins * 0.05)
                    reason = f"Đã thắng {wins} lần, có {has_price} bản giá"
                elif wins > 0 and actual_price:
                    decision, confidence = "yes", 0.7
                    reason = f"Thắng {wins} lần, giá thực tế ${actual_price:.2f}"
                elif wins > 0:
                    decision, confidence = "maybe", 0.55
                    reason = f"Thắng {wins} lần nhưng chưa có giá gần đây"
                elif losses >= 3:
                    decision, confidence = "no", 0.8
                    reason = f"Đã thua {losses} lần liên tiếp"
                elif has_price > 0 and similar_wins > similar_total * 0.4:
                    decision, confidence = "maybe", 0.5
                    reason = f"Có giá, maker tương tự thắng {similar_wins}/{similar_total}"
                elif similar_total > 5 and similar_wins < similar_total * 0.2:
                    decision, confidence = "no", 0.6
                    reason = f"Maker này tỷ lệ thắng thấp ({similar_wins}/{similar_total})"
                else:
                    decision, confidence = "maybe", 0.3
                    reason = "Chưa có lịch sử — cần xem xét thủ công"

                results.append({
                    "bqms_code": bqms, "spec": spec, "maker": maker,
                    "decision": decision, "confidence": confidence, "reason": reason,
                    "detail": {"wins": wins, "losses": losses, "has_price": has_price,
                               "actual_price_usd": float(actual_price) if actual_price else None,
                               "similar_wins": similar_wins, "similar_total": similar_total},
                })

                _jobs[job_id]["progress"] = int((i + 1) / len(orders) * 100)
                _log(job_id, f"[{i+1}/{len(orders)}] {bqms}: {decision} ({confidence:.0%}) — {reason}")

            _jobs[job_id]["result"] = {
                "results": results,
                "summary": {"total": len(results),
                            "yes": sum(1 for r in results if r["decision"] == "yes"),
                            "no": sum(1 for r in results if r["decision"] == "no"),
                            "maybe": sum(1 for r in results if r["decision"] == "maybe")},
            }
            _jobs[job_id]["status"] = "done"
            _log(job_id, "Hoàn thành phân loại!")
        except Exception as e:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(e)
        finally:
            await conn.close()

    background_tasks.add_task(_run)
    return {"job_id": job_id}


# ═══════════════════════════════════════════════════════
# TOOL 5: KHẢO GIÁ THỊ TRƯỜNG
# Tìm kiếm giá từ toàn bộ DB nội bộ
# ═══════════════════════════════════════════════════════

@router.post("/tool5/search")
async def tool5_search(
    body: dict,
    background_tasks: BackgroundTasks,
    conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    """Khảo giá: tìm tất cả thông tin liên quan đến sản phẩm."""
    job_id = _new_job("market_search")
    spec = body.get("spec", "")
    bqms_code = body.get("bqms_code", "")

    async def _run():
        conn = await _get_conn()
        try:
            query = bqms_code or spec
            _log(job_id, f"Bắt đầu khảo giá: {query}")

            # Phase 1: Tìm sản phẩm trong DB
            _log(job_id, "📦 Đang tìm sản phẩm trong cơ sở dữ liệu...")
            if bqms_code:
                products = await conn.fetch(
                    "SELECT * FROM products WHERE bqms_code = $1", bqms_code)
            else:
                products = await conn.fetch(
                    "SELECT * FROM products WHERE spec ILIKE $1 OR product_name ILIKE $1 LIMIT 20",
                    f"%{spec[:50]}%")
            _log(job_id, f"  → {len(products)} sản phẩm")

            # Phase 2: Lịch sử báo giá
            _log(job_id, "💰 Đang tra cứu lịch sử báo giá...")
            if bqms_code:
                quotes = await conn.fetch(
                    """SELECT date, rfq_no, bqms_code, spec, maker, supplier,
                              price_bqms_v1, price_bqms_v2, price_bqms_v3, price_bqms_v4, result
                       FROM quotations WHERE bqms_code = $1 ORDER BY date DESC LIMIT 20""", bqms_code)
            else:
                quotes = await conn.fetch(
                    """SELECT date, rfq_no, bqms_code, spec, maker, supplier,
                              price_bqms_v1, price_bqms_v2, price_bqms_v3, price_bqms_v4, result
                       FROM quotations WHERE spec ILIKE $1 ORDER BY date DESC LIMIT 20""",
                    f"%{spec[:50]}%")
            _log(job_id, f"  → {len(quotes)} bản báo giá")

            # Phase 3: Giá mua thực tế
            _log(job_id, "📊 Đang tra cứu giá mua thực tế...")
            if bqms_code:
                actual = await conn.fetch(
                    """SELECT transaction_date, bqms_code, spec, maker,
                              unit_price_usd, unit_price_vnd, seller, buyer, quantity
                       FROM transactions WHERE bqms_code = $1 AND unit_price_usd IS NOT NULL
                       ORDER BY transaction_date DESC LIMIT 15""", bqms_code)
            else:
                actual = await conn.fetch(
                    """SELECT transaction_date, bqms_code, spec, maker,
                              unit_price_usd, unit_price_vnd, seller, buyer, quantity
                       FROM transactions WHERE spec ILIKE $1 AND unit_price_usd IS NOT NULL
                       ORDER BY transaction_date DESC LIMIT 15""",
                    f"%{spec[:50]}%")
            _log(job_id, f"  → {len(actual)} giao dịch có giá")

            # Phase 4: Giá thị trường đã lưu
            _log(job_id, "🌐 Đang kiểm tra giá thị trường...")
            market = await conn.fetch(
                """SELECT * FROM market_prices
                   WHERE product_name ILIKE $1 OR spec ILIKE $1 OR bqms_code = $2
                   ORDER BY created_at DESC LIMIT 10""",
                f"%{spec[:50]}%", bqms_code or "")
            _log(job_id, f"  → {len(market)} giá thị trường")

            # Phase 5: Phân tích giá
            _log(job_id, "🔍 Đang phân tích...")
            all_usd = [float(r["unit_price_usd"]) for r in actual if r["unit_price_usd"]]
            quote_v1 = [float(r["price_bqms_v1"]) for r in quotes if r["price_bqms_v1"]]

            analysis = {
                "actual_price_avg": round(sum(all_usd) / len(all_usd), 4) if all_usd else None,
                "actual_price_min": round(min(all_usd), 4) if all_usd else None,
                "actual_price_max": round(max(all_usd), 4) if all_usd else None,
                "quote_v1_avg": round(sum(quote_v1) / len(quote_v1), 4) if quote_v1 else None,
                "data_points": len(all_usd),
                "quote_points": len(quote_v1),
                "unique_sellers": len(set(r["seller"] for r in actual if r["seller"])),
                "unique_suppliers": len(set(r["supplier"] for r in quotes if r["supplier"])),
            }

            # NCC ranking
            ncc_stats = {}
            for r in quotes:
                s = r["supplier"]
                if not s:
                    continue
                if s not in ncc_stats:
                    ncc_stats[s] = {"total": 0, "wins": 0, "prices": []}
                ncc_stats[s]["total"] += 1
                if r["result"] in ("Y", "y"):
                    ncc_stats[s]["wins"] += 1
                if r["price_bqms_v1"]:
                    ncc_stats[s]["prices"].append(float(r["price_bqms_v1"]))

            supplier_ranking = sorted([
                {"name": k, "total": v["total"], "wins": v["wins"],
                 "win_rate": round(v["wins"] / v["total"] * 100, 1) if v["total"] else 0,
                 "avg_price": round(sum(v["prices"]) / len(v["prices"]), 4) if v["prices"] else None}
                for k, v in ncc_stats.items()
            ], key=lambda x: x["wins"], reverse=True)

            _log(job_id, f"Hoàn thành! {analysis['data_points']} giá thực tế, {analysis['unique_sellers']} bên bán")

            _jobs[job_id]["result"] = {
                "query": query,
                "products": [dict(r) for r in products],
                "quotes": [dict(r) for r in quotes],
                "actual_prices": [dict(r) for r in actual],
                "market_prices": [dict(r) for r in market],
                "analysis": analysis,
                "supplier_ranking": supplier_ranking,
            }
            _jobs[job_id]["status"] = "done"

        except Exception as e:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(e)
            _log(job_id, f"Lỗi: {e}")
        finally:
            await conn.close()

    background_tasks.add_task(_run)
    return {"job_id": job_id}


# ═══════════════════════════════════════════════════════
# JOB STATUS (shared)
# ═══════════════════════════════════════════════════════

@router.get("/job/{job_id}")
async def get_job(job_id: str, _=Depends(get_current_user)):
    if job_id not in _jobs:
        raise NotFoundError("Job", job_id)
    return _jobs[job_id]
