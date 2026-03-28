"""FastAPI dependencies — DB connection, current user, role guards."""

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from ..db.session import get_db
from ..domain.enums import UserRole
from ..domain.exceptions import AuthError, PermissionError as PermError
from ..services.auth_service import AuthService
from ..repositories.user_repo import UserRepository
from ..repositories.audit_repo import AuditRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    conn=Depends(get_db),
) -> dict:
    user_repo = UserRepository(conn)
    audit_repo = AuditRepository(conn)
    auth = AuthService(user_repo, audit_repo)
    try:
        return await auth.get_current_user(token)
    except Exception:
        raise AuthError("Invalid or expired token")


def require_role(*roles: UserRole):
    """Dependency factory: only allow specified roles."""
    async def _guard(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role", "")
        if user_role not in [r.value if isinstance(r, UserRole) else r for r in roles]:
            raise PermError(f"Role '{user_role}' cannot access this resource")
        return user
    return _guard


def require_any_authenticated(user: dict = Depends(get_current_user)) -> dict:
    return user
