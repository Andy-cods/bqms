"""Song Chau ERP — Application Factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import get_settings
from .db.session import create_pool, close_pool
from .api.v1.router import api_router
from .domain.exceptions import DomainError
from .middleware.error_handler import domain_error_handler, generic_error_handler
from .middleware.rate_limit import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_pool()
    yield
    await close_pool()


def create_app() -> FastAPI:
    s = get_settings()

    app = FastAPI(
        title=s.app_title,
        version=s.app_version,
        docs_url="/docs" if s.debug or s.app_env != "production" else "/docs",
        lifespan=lifespan,
    )

    # Middleware (order matters: last added = first executed)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if s.app_env == "development" else [
            "http://123.30.48.127",
            "https://123.30.48.127",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware, max_per_second=s.rate_limit_per_second)

    # Exception handlers
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    # API routes
    app.include_router(api_router)

    # Health at root level (no auth)
    @app.get("/api/health")
    async def health_root():
        from .db.session import get_db
        async for conn in get_db():
            ver = await conn.fetchval("SELECT version()")
            tables = await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"
            )
            return {
                "status": "ok", "database": "connected",
                "postgres_version": ver.split(",")[0] if ver else "unknown",
                "tables": tables,
            }

    # Serve frontend
    import os
    static_dir = os.path.join(os.path.dirname(__file__), "static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(static_dir, "index.html"))

    return app


app = create_app()
