"""In-memory rate limiter — no Redis needed for 3-5 users."""

import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_per_second: int = 30):
        super().__init__(app)
        self.max_per_second = max_per_second
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Clean old entries
        self._requests[ip] = [t for t in self._requests[ip] if now - t < 1.0]

        if len(self._requests[ip]) >= self.max_per_second:
            return JSONResponse(
                status_code=429,
                content={"success": False, "error": "Too many requests", "code": "RATE_LIMITED"},
            )

        self._requests[ip].append(now)

        # Periodic cleanup (every 100 requests)
        if sum(len(v) for v in self._requests.values()) > 1000:
            self._cleanup(now)

        return await call_next(request)

    def _cleanup(self, now: float) -> None:
        stale = [ip for ip, ts in self._requests.items() if not ts or now - ts[-1] > 60]
        for ip in stale:
            del self._requests[ip]
