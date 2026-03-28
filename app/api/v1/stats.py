"""Stats and health endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ...db.session import get_db
from ...domain.models import StatsResponse
from ...repositories.audit_repo import StatsRepository
from ..deps import require_any_authenticated

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(conn=Depends(get_db)):
    ver = await conn.fetchval("SELECT version()")
    table_count = await conn.fetchval(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"
    )
    return {
        "status": "ok",
        "database": "connected",
        "postgres_version": ver.split(",")[0] if ver else "unknown",
        "tables": table_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/stats", response_model=StatsResponse)
async def stats(conn=Depends(get_db), _=Depends(require_any_authenticated)):
    counts = await StatsRepository(conn).get_all_counts()
    return StatsResponse(
        transactions=counts.get("transactions", 0),
        products=counts.get("products", 0),
        purchase_orders=counts.get("purchase_orders", 0),
        rfq_count=counts.get("rfq", 0),
        deliveries=counts.get("deliveries", 0),
        market_prices=counts.get("market_prices", 0),
        users=counts.get("users", 0),
    )


@router.get("/audit-log")
async def audit_log(
    page: int = 1, limit: int = 50, conn=Depends(get_db),
    _=Depends(require_any_authenticated),
):
    from ...repositories.audit_repo import AuditRepository
    rows, total = await AuditRepository(conn).list_recent(page, limit)
    return {"data": rows, "total": total, "page": page, "pages": (total + limit - 1) // limit}
