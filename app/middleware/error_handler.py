"""Global exception handler — convert domain errors to JSON responses."""

from fastapi import Request
from fastapi.responses import JSONResponse

from ..domain.exceptions import (
    DomainError, NotFoundError, AuthError,
    PermissionError, ValidationError, RateLimitError,
)

STATUS_MAP = {
    "NOT_FOUND": 404,
    "AUTH_ERROR": 401,
    "PERMISSION_DENIED": 403,
    "VALIDATION_ERROR": 422,
    "RATE_LIMITED": 429,
    "DOMAIN_ERROR": 400,
}


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    status = STATUS_MAP.get(exc.code, 400)
    return JSONResponse(
        status_code=status,
        content={"success": False, "error": exc.message, "code": exc.code},
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error", "code": "INTERNAL"},
    )
