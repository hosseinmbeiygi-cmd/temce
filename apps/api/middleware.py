from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging import get_logger

logger = get_logger(__name__)


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.monotonic()
        response = await call_next(request)
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
