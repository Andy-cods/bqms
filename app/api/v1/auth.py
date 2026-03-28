"""Auth endpoints — login, refresh, me, change password."""

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

from ...db.session import get_db
from ...domain.models import LoginRequest, ChangePasswordRequest
from ...services.auth_service import AuthService
from ...repositories.user_repo import UserRepository
from ...repositories.audit_repo import AuditRepository
from ..deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_service(conn=Depends(get_db)) -> AuthService:
    return AuthService(UserRepository(conn), AuditRepository(conn))


@router.post("/login")
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    svc: AuthService = Depends(_auth_service),
):
    ip = request.client.host if request.client else ""
    return await svc.login(form.username, form.password, ip)


@router.post("/refresh")
async def refresh(refresh_token: str, svc: AuthService = Depends(_auth_service)):
    return await svc.refresh(refresh_token)


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "id": str(user["id"]), "email": user["email"],
        "name": user["full_name"], "role": user["role"],
        "department": user.get("department"),
    }


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
    svc: AuthService = Depends(_auth_service),
):
    await svc.change_password(user["id"], body.old_password, body.new_password)
    return {"success": True, "message": "Password changed"}
