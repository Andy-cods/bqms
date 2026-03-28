"""Purchase Order endpoints."""

from fastapi import APIRouter, Depends

from ...db.session import get_db
from ...domain.models import POCreate, POLineItemCreate
from ...domain.enums import UserRole
from ...domain.exceptions import NotFoundError
from ...repositories.po_repo import PORepository
from ..deps import get_current_user, require_role

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


@router.get("")
async def list_pos(
    status: str = "", supplier_id: int = 0,
    page: int = 1, limit: int = 50,
    conn=Depends(get_db), _=Depends(get_current_user),
):
    repo = PORepository(conn)
    rows, total = await repo.search(status, supplier_id, page, limit)
    return {"data": rows, "total": total, "page": page, "pages": (total + limit - 1) // limit}


@router.get("/{po_id}")
async def get_po(po_id: int, conn=Depends(get_db), _=Depends(get_current_user)):
    repo = PORepository(conn)
    po = await repo.get_by_id(po_id)
    if not po:
        raise NotFoundError("PurchaseOrder", str(po_id))
    items = await repo.get_line_items(po_id)
    return {**po, "line_items": items}


@router.post("", status_code=201)
async def create_po(
    body: POCreate, conn=Depends(get_db),
    user=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    repo = PORepository(conn)
    return await repo.create(body.model_dump(), user["id"])


@router.patch("/{po_id}/status")
async def update_po_status(
    po_id: int, status: str, conn=Depends(get_db),
    user=Depends(require_role(UserRole.admin, UserRole.manager)),
):
    repo = PORepository(conn)
    approved_by = user["id"] if status == "approved" else None
    po = await repo.update_status(po_id, status, approved_by)
    if not po:
        raise NotFoundError("PurchaseOrder", str(po_id))
    return po


@router.post("/{po_id}/line-items", status_code=201)
async def add_line_item(
    po_id: int, body: POLineItemCreate, conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    repo = PORepository(conn)
    po = await repo.get_by_id(po_id)
    if not po:
        raise NotFoundError("PurchaseOrder", str(po_id))
    return await repo.add_line_item(po_id, body.model_dump())
