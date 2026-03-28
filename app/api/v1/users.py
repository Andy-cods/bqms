"""User management — admin only."""

from fastapi import APIRouter, Depends
from uuid import UUID

from ...db.session import get_db
from ...domain.models import UserCreate, UserUpdate, UserOut
from ...domain.enums import UserRole
from ...services.auth_service import AuthService
from ...repositories.user_repo import UserRepository
from ...repositories.audit_repo import AuditRepository
from ..deps import require_role

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/")
async def list_users(
    page: int = 1, limit: int = 50,
    conn=Depends(get_db),
    _=Depends(require_role(UserRole.admin)),
):
    repo = UserRepository(conn)
    rows, total = await repo.list_all(page, limit)
    # Strip password hashes
    data = [
        {k: (str(v) if k == "id" else v) for k, v in r.items() if k != "hashed_pw"}
        for r in rows
    ]
    return {"data": data, "total": total, "page": page, "pages": (total + limit - 1) // limit}


@router.post("/", status_code=201)
async def create_user(
    body: UserCreate,
    conn=Depends(get_db),
    admin=Depends(require_role(UserRole.admin)),
):
    svc = AuthService(UserRepository(conn), AuditRepository(conn))
    user = await svc.create_user(body.model_dump())
    await AuditRepository(conn).log(
        admin["id"], "USER_CREATED", "users", str(user["id"]),
        new_data={"email": user["email"], "role": user["role"]},
    )
    return {k: (str(v) if k == "id" else v) for k, v in user.items() if k != "hashed_pw"}


@router.put("/{user_id}")
async def update_user(
    user_id: UUID, body: UserUpdate,
    conn=Depends(get_db),
    admin=Depends(require_role(UserRole.admin)),
):
    repo = UserRepository(conn)
    update_data = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "role" in update_data:
        update_data["role"] = update_data["role"].value if hasattr(update_data["role"], "value") else update_data["role"]
    user = await repo.update(user_id, update_data)
    if not user:
        from ...domain.exceptions import NotFoundError
        raise NotFoundError("User", str(user_id))
    await AuditRepository(conn).log(
        admin["id"], "USER_UPDATED", "users", str(user_id), new_data=update_data,
    )
    return {k: (str(v) if k == "id" else v) for k, v in user.items() if k != "hashed_pw"}
