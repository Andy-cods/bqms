"""User repository — database access for users table."""

from typing import Optional
from uuid import UUID

from .base import BaseRepository


class UserRepository(BaseRepository):

    async def get_by_email(self, email: str) -> Optional[dict]:
        row = await self.conn.fetchrow(
            "SELECT * FROM users WHERE email = $1", email,
        )
        return dict(row) if row else None

    async def get_by_id(self, user_id: UUID) -> Optional[dict]:
        row = await self.conn.fetchrow(
            "SELECT * FROM users WHERE id = $1", user_id,
        )
        return dict(row) if row else None

    async def create(self, data: dict) -> dict:
        row = await self.conn.fetchrow(
            """INSERT INTO users (email, full_name, role, department, hashed_pw)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING *""",
            data["email"], data["full_name"], data["role"],
            data.get("department"), data["hashed_pw"],
        )
        return dict(row)

    async def update(self, user_id: UUID, data: dict) -> Optional[dict]:
        sets, params, idx = [], [], 1
        for key in ("full_name", "role", "department", "is_active", "hashed_pw"):
            if key in data and data[key] is not None:
                sets.append(f"{key} = ${idx}")
                params.append(data[key])
                idx += 1
        if not sets:
            return await self.get_by_id(user_id)

        params.append(user_id)
        sql = f"UPDATE users SET {', '.join(sets)} WHERE id = ${idx} RETURNING *"
        row = await self.conn.fetchrow(sql, *params)
        return dict(row) if row else None

    async def update_last_login(self, user_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE users SET last_login = NOW() WHERE id = $1", user_id,
        )

    async def list_all(self, page: int = 1, limit: int = 50) -> tuple[list[dict], int]:
        return await self._fetch_page("users", page, limit, order_by="created_at DESC")

    async def count(self) -> int:
        return await self.conn.fetchval("SELECT COUNT(*) FROM users") or 0
