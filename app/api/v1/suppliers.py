"""Supplier + Delivery + RFQ endpoints."""

from fastapi import APIRouter, Depends

from ...db.session import get_db
from ...domain.models import SupplierCreate, DeliveryCreate, RFQCreate
from ...domain.enums import UserRole
from ...domain.exceptions import NotFoundError
from ..deps import get_current_user, require_role

router = APIRouter(tags=["data"])


# ── Suppliers ───────────────────────────────────────────

@router.get("/suppliers")
async def list_suppliers(
    q: str = "", page: int = 1, limit: int = 50,
    conn=Depends(get_db), _=Depends(get_current_user),
):
    offset = (page - 1) * min(limit, 100)
    if q:
        rows = await conn.fetch(
            "SELECT * FROM suppliers WHERE name ILIKE $1 OR code ILIKE $1 ORDER BY name LIMIT $2 OFFSET $3",
            f"%{q}%", min(limit, 100), offset,
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM suppliers WHERE name ILIKE $1 OR code ILIKE $1", f"%{q}%",
        )
    else:
        rows = await conn.fetch("SELECT * FROM suppliers ORDER BY name LIMIT $1 OFFSET $2", min(limit, 100), offset)
        total = await conn.fetchval("SELECT COUNT(*) FROM suppliers")
    return {"data": [dict(r) for r in rows], "total": total, "page": page}


@router.post("/suppliers", status_code=201)
async def create_supplier(
    body: SupplierCreate, conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    row = await conn.fetchrow(
        """INSERT INTO suppliers (name, code, contact_email, contact_phone, country, payment_terms)
           VALUES ($1,$2,$3,$4,$5,$6) RETURNING *""",
        body.name, body.code, body.contact_email, body.contact_phone, body.country, body.payment_terms,
    )
    return dict(row)


# ── Deliveries (po_deliveries) ──────────────────────────

@router.get("/deliveries")
async def list_deliveries(
    po_number: str = "", status: str = "", page: int = 1, limit: int = 50,
    conn=Depends(get_db), _=Depends(get_current_user),
):
    conditions, params, idx = [], [], 1
    if po_number:
        conditions.append(f"po_number ILIKE ${idx}")
        params.append(f"%{po_number}%")
        idx += 1
    if status:
        conditions.append(f"status ILIKE ${idx}")
        params.append(f"%{status}%")
        idx += 1
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * min(limit, 100)

    total = await conn.fetchval(f"SELECT COUNT(*) FROM po_deliveries {where}", *params)
    rows = await conn.fetch(
        f"SELECT * FROM po_deliveries {where} ORDER BY po_date DESC NULLS LAST LIMIT ${idx} OFFSET ${idx+1}",
        *params, min(limit, 100), offset,
    )
    return {"data": [dict(r) for r in rows], "total": total, "page": page}


# ── Quotations ──────────────────────────────────────────

@router.get("/quotations")
async def list_quotations(
    q: str = "", result: str = "", page: int = 1, limit: int = 50,
    conn=Depends(get_db), _=Depends(get_current_user),
):
    conditions, params, idx = [], [], 1
    if q:
        conditions.append(f"(rfq_no ILIKE ${idx} OR bqms_code ILIKE ${idx} OR spec ILIKE ${idx})")
        params.append(f"%{q}%")
        idx += 1
    if result:
        conditions.append(f"result = ${idx}")
        params.append(result)
        idx += 1
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * min(limit, 100)

    total = await conn.fetchval(f"SELECT COUNT(*) FROM quotations {where}", *params)
    rows = await conn.fetch(
        f"SELECT * FROM quotations {where} ORDER BY date DESC NULLS LAST LIMIT ${idx} OFFSET ${idx+1}",
        *params, min(limit, 100), offset,
    )
    return {"data": [dict(r) for r in rows], "total": total, "page": page}


# ── Order Tracking ──────────────────────────────────────

@router.get("/orders")
async def list_orders(
    page: int = 1, limit: int = 50,
    conn=Depends(get_db), _=Depends(get_current_user),
):
    offset = (page - 1) * min(limit, 100)
    total = await conn.fetchval("SELECT COUNT(*) FROM order_tracking")
    rows = await conn.fetch(
        "SELECT * FROM order_tracking ORDER BY order_date DESC NULLS LAST LIMIT $1 OFFSET $2",
        min(limit, 100), offset,
    )
    return {"data": [dict(r) for r in rows], "total": total, "page": page}
