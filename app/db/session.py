"""asyncpg connection pool management."""

import asyncpg
from typing import Optional, AsyncGenerator

from ..config import get_settings

pool: Optional[asyncpg.Pool] = None


async def create_pool() -> asyncpg.Pool:
    global pool
    s = get_settings()
    dsn = s.database_url.replace("+asyncpg", "")
    pool = await asyncpg.create_pool(
        dsn, min_size=s.db_pool_min, max_size=s.db_pool_max,
    )
    return pool


async def close_pool() -> None:
    global pool
    if pool:
        await pool.close()
        pool = None


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    if pool is None:
        await create_pool()
    async with pool.acquire() as conn:  # type: ignore[union-attr]
        yield conn


async def get_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        await create_pool()
    return pool  # type: ignore[return-value]
