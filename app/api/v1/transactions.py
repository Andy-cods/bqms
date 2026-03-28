"""Transaction endpoints — list/search (ETL inserts data)."""

from fastapi import APIRouter, Depends

from ...db.session import get_db
from ...repositories.transaction_repo import TransactionRepository
from ..deps import require_any_authenticated

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
async def list_transactions(
    q: str = "", date_from: str = "", date_to: str = "",
    page: int = 1, limit: int = 50,
    conn=Depends(get_db), _=Depends(require_any_authenticated),
):
    repo = TransactionRepository(conn)
    rows, total = await repo.search(q, date_from, date_to, page, limit)
    return {"data": rows, "total": total, "page": page, "pages": (total + limit - 1) // limit}
