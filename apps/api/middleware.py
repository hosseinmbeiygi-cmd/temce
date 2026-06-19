from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings as app_settings
from core.logging import get_logger
from core.rate_limit import get_rate_limiter

logger = get_logger(__name__)


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.monotonic() - start
            logger.exception("Unhandled exception processing %s %s (%.3fs)", request.method, request.url.path, elapsed)
            raise
        elapsed = time.monotonic() - start
        logger.info("%s %s -> %d (%.3fs)", request.method, request.url.path, response.status_code, elapsed)
        response.headers["X-Response-Time-Ms"] = str(round(elapsed * 1000))
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        logger.debug("Request: %s %s", request.method, request.url.path)
        response = await call_next(request)
        logger.debug("Response: %d", response.status_code)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_calls: int = 0, window_seconds: float = 60.0):
        super().__init__(app)
        self.max_calls = max_calls or app_settings.provider_rate_limit_per_minute
        self.window_seconds = window_seconds
        self._limiter = get_rate_limiter()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path.startswith(("/docs", "/openapi.json", "/api/v1/health")):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"api:{client_ip}:{request.url.path}"

        if not self._limiter.allow():
            from fastapi.responses import JSONResponse

            logger.warning("Rate limit exceeded for %s", client_ip)
            return JSONResponse(
                status_code=429,
                content={"success": False, "error": "Rate limit exceeded", "code": "RATE_LIMIT"},
                headers={"Retry-After": str(int(self.window_seconds))},
            )

        return await call_next(request)
