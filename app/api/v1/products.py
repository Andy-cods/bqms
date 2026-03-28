"""Product CRUD endpoints."""

from fastapi import APIRouter, Depends

from ...db.session import get_db
from ...domain.models import ProductCreate, ProductUpdate
from ...domain.enums import UserRole
from ...domain.exceptions import NotFoundError
from ...repositories.product_repo import ProductRepository
from ..deps import require_any_authenticated, require_role

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
async def list_products(
    q: str = "", type: str = "", page: int = 1, limit: int = 50,
    conn=Depends(get_db), _=Depends(require_any_authenticated),
):
    repo = ProductRepository(conn)
    rows, total = await repo.search(q, type, page, limit)
    return {"data": rows, "total": total, "page": page, "pages": (total + limit - 1) // limit}


@router.get("/{product_id}")
async def get_product(
    product_id: int, conn=Depends(get_db), _=Depends(require_any_authenticated),
):
    repo = ProductRepository(conn)
    product = await repo.get_by_id(product_id)
    if not product:
        raise NotFoundError("Product", str(product_id))
    return product


@router.post("", status_code=201)
async def create_product(
    body: ProductCreate, conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    repo = ProductRepository(conn)
    return await repo.create(body.model_dump())


@router.put("/{product_id}")
async def update_product(
    product_id: int, body: ProductUpdate, conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin, UserRole.procurement)),
):
    repo = ProductRepository(conn)
    product = await repo.update(product_id, body.model_dump(exclude_none=True))
    if not product:
        raise NotFoundError("Product", str(product_id))
    return product


@router.delete("/{product_id}")
async def delete_product(
    product_id: int, conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin)),
):
    repo = ProductRepository(conn)
    if not await repo.delete(product_id):
        raise NotFoundError("Product", str(product_id))
    return {"success": True}
