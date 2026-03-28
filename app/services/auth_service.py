"""Auth service — JWT tokens, password hashing, RBAC."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import jwt, JWTError
from passlib.context import CryptContext

from ..config import get_settings
from ..domain.exceptions import AuthError
from ..repositories.user_repo import UserRepository
from ..repositories.audit_repo import AuditRepository

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def create_token(data: dict, expires_seconds: int) -> str:
    s = get_settings()
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(seconds=expires_seconds)
    return jwt.encode(to_encode, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError as e:
        raise AuthError(f"Invalid token: {e}")


class AuthService:
    def __init__(self, user_repo: UserRepository, audit_repo: AuditRepository):
        self.user_repo = user_repo
        self.audit_repo = audit_repo

    async def login(self, email: str, password: str, ip: str = "") -> dict:
        user = await self.user_repo.get_by_email(email)
        if not user or not user.get("is_active", False):
            await self.audit_repo.log(
                None, "LOGIN_FAILED", "users", email, ip_address=ip,
            )
            raise AuthError("Invalid credentials")

        if not verify_password(password, user["hashed_pw"]):
            await self.audit_repo.log(
                user["id"], "LOGIN_FAILED", "users", email, ip_address=ip,
            )
            raise AuthError("Invalid credentials")

        s = get_settings()
        token_data = {
            "sub": str(user["id"]),
            "role": user["role"],
            "name": user["full_name"],
        }
        access = create_token(token_data, s.access_token_expire)
        refresh = create_token(
            {**token_data, "type": "refresh"}, s.refresh_token_expire,
        )

        await self.user_repo.update_last_login(user["id"])
        await self.audit_repo.log(
            user["id"], "LOGIN_SUCCESS", "users", str(user["id"]), ip_address=ip,
        )

        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "user": {
                "id": str(user["id"]),
                "email": user["email"],
                "name": user["full_name"],
                "role": user["role"],
            },
        }

    async def refresh(self, refresh_token: str) -> dict:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise AuthError("Not a refresh token")

        user_id = payload.get("sub")
        user = await self.user_repo.get_by_id(UUID(user_id))
        if not user or not user.get("is_active"):
            raise AuthError("User not found or inactive")

        s = get_settings()
        token_data = {
            "sub": str(user["id"]),
            "role": user["role"],
            "name": user["full_name"],
        }
        access = create_token(token_data, s.access_token_expire)
        refresh_new = create_token(
            {**token_data, "type": "refresh"}, s.refresh_token_expire,
        )
        return {
            "access_token": access,
            "refresh_token": refresh_new,
            "token_type": "bearer",
            "user": {
                "id": str(user["id"]),
                "email": user["email"],
                "name": user["full_name"],
                "role": user["role"],
            },
        }

    async def get_current_user(self, token: str) -> dict:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise AuthError("Invalid token payload")

        user = await self.user_repo.get_by_id(UUID(user_id))
        if not user or not user.get("is_active"):
            raise AuthError("User not found or inactive")
        return user

    async def change_password(
        self, user_id: UUID, old_password: str, new_password: str,
    ) -> bool:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AuthError("User not found")
        if not verify_password(old_password, user["hashed_pw"]):
            raise AuthError("Current password is incorrect")
        new_hash = hash_password(new_password)
        await self.user_repo.update(user_id, {"hashed_pw": new_hash})
        await self.audit_repo.log(
            user_id, "PASSWORD_CHANGED", "users", str(user_id),
        )
        return True

    async def create_user(self, data: dict) -> dict:
        existing = await self.user_repo.get_by_email(data["email"])
        if existing:
            raise AuthError(f"Email '{data['email']}' already registered")
        data["hashed_pw"] = hash_password(data.pop("password"))
        user = await self.user_repo.create(data)
        return user
