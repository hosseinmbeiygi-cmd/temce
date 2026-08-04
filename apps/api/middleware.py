from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.config import settings as app_settings
from core.logging import get_logger
from core.rate_limit import get_rate_limiter
from core.security.tokens import decode_access_token, is_token_revoked

logger = get_logger(__name__)


# Paths that are exempt from security header enforcement
_EXEMPT_PATHS = ("/docs", "/redoc", "/openapi.json", "/api/v1/health")

# Sensitive write endpoints that require auth (defense-in-depth at middleware level)
_SENSITIVE_WRITE_PREFIXES = (
    "/api/v1/backtests/run",
    "/api/v1/backtests/generate",
    "/api/v1/backtests/cascade",
    "/api/v1/backtests/adaptive",
    "/api/v1/ml/train",
    "/api/v1/ml/predict",
    "/api/v1/portfolios",
    "/api/v1/alerts",
    "/api/v1/data-import",
    "/api/v1/signal-insights",
)


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


class SecurityMiddleware(BaseHTTPMiddleware):
    """Defense-in-depth security middleware.

    Adds security headers to all responses and validates auth on sensitive
    write endpoints at the middleware level (supplements router-level deps).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Defense-in-depth: check auth FIRST on sensitive write endpoints
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            for prefix in _SENSITIVE_WRITE_PREFIXES:
                if path.startswith(prefix):
                    auth_header = request.headers.get("authorization", "")
                    if not auth_header.startswith("Bearer "):
                        logger.warning("Unauthenticated access to sensitive endpoint: %s %s", request.method, path)
                        return JSONResponse(
                            status_code=401,
                            content={"success": False, "error": "Authentication required for this endpoint", "code": "AUTH_REQUIRED"},
                        )
                    # Validate the token at middleware level (signature + revocation)
                    token = auth_header.split(" ")[1]
                    try:
                        payload = decode_access_token(token)
                        if await is_token_revoked(payload.get("jti")):
                            return JSONResponse(
                                status_code=401,
                                content={"success": False, "error": "Token has been revoked", "code": "TOKEN_REVOKED"},
                            )
                    except Exception:
                        return JSONResponse(
                            status_code=401,
                            content={"success": False, "error": "Invalid or expired token", "code": "INVALID_TOKEN"},
                        )
                    break

        response = await call_next(request)

        # Add security headers (skip docs/openapi)
        if not path.startswith(_EXEMPT_PATHS):
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """Cross-Site Request Forgery protection (enabled via ``enable_csrf``).

    The API is stateless (JWT bearer tokens, no cookies), so the classic CSRF
    vector — browsers silently attaching cookies to state-changing requests —
    does not apply to authenticated API calls. The remaining risk is
    *unauthenticated* state-changing requests (login, register, cron toggles)
    being triggered cross-site.

    Mitigation implemented here: for unsafe methods (POST/PUT/PATCH/DELETE)
    requests carrying an Origin or Referer header are only allowed when the
    header's host matches the configured ``cors_origins``. Requests without
    either header (curl, server-to-server) are treated as non-browser and
    allowed. Safe methods (GET/HEAD/OPTIONS) and health/docs paths pass
    through untouched.

    No-op when ``settings.enable_csrf`` is False.
    """

    _UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not app_settings.enable_csrf:
            return await call_next(request)

        if request.method in self._UNSAFE_METHODS:
            if request.url.path.startswith(("/docs", "/openapi.json", "/api/v1/health")):
                return await call_next(request)

            origin = request.headers.get("origin") or request.headers.get("referer")
            if origin:
                if not self._origin_allowed(origin):
                    logger.warning(
                        "CSRF blocked: %s %s from origin %s",
                        request.method, request.url.path, origin,
                    )
                    return JSONResponse(
                        status_code=403,
                        content={
                            "success": False,
                            "error": "Cross-site request blocked",
                            "code": "CSRF_BLOCKED",
                        },
                    )

        return await call_next(request)

    def _origin_allowed(self, origin: str) -> bool:
        """Match an Origin/Referer against the configured CORS origins.

        ``*`` means any origin is acceptable (same semantic as CORS).
        Referer includes a path suffix; we compare scheme://host[:port] only.
        """
        from urllib.parse import urlparse

        if "*" in app_settings.cors_origins:
            return True
        try:
            origin_base = f"{urlparse(origin).scheme}://{urlparse(origin).netloc}".lower()
        except Exception:
            return False
        for allowed in app_settings.cors_origins:
            try:
                allowed_base = f"{urlparse(allowed).scheme}://{urlparse(allowed).netloc}".lower()
            except Exception:
                allowed_base = allowed.lower()
            if origin_base == allowed_base:
                return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-endpoint rate limiting middleware.

    Checks endpoint_rate_limits config for per-path limits, falls back to
    provider_rate_limit_per_minute for unconfigured endpoints.
    Uses a sliding-window algorithm via RateLimiter.
    """

    def __init__(self, app, window_seconds: float = 60.0):
        super().__init__(app)
        self.window_seconds = window_seconds
        self._limiter = get_rate_limiter()
        # Build endpoint -> max_calls map from config
        self._endpoint_limits: dict[str, int] = dict(app_settings.endpoint_rate_limits)

    def _get_limit_for_path(self, path: str) -> int:
        """Find the rate limit for a path, checking exact match then prefix match."""
        # Exact match first
        if path in self._endpoint_limits:
            return self._endpoint_limits[path]
        # Prefix match (longest prefix wins)
        best_match = ""
        best_limit = app_settings.provider_rate_limit_per_minute
        for pattern, limit in self._endpoint_limits.items():
            if path.startswith(pattern) and len(pattern) > len(best_match):
                best_match = pattern
                best_limit = limit
        return best_limit

    def _get_key(self, client_ip: str, path: str) -> str:
        """Generate a rate limit key for a client+path combination."""
        return f"api:{client_ip}:{path}"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if app_settings.environment == "test" or request.url.path.startswith(
            ("/docs", "/openapi.json", "/api/v1/health", "/metrics")
        ):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        max_calls = self._get_limit_for_path(path)
        key = self._get_key(client_ip, path)

        # Ensure the limit is registered (only once per key, then reused)
        if not self._limiter.has_limit(key):
            self._limiter.set_limit(
                key,
                rate=max_calls / self.window_seconds,
                burst=max_calls,
                window_seconds=self.window_seconds,
            )

        if not self._limiter.allow(key):
            logger.warning("Rate limit exceeded: %s %s from %s (limit: %d/min)", request.method, path, client_ip, max_calls)
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": "Rate limit exceeded",
                    "code": "RATE_LIMIT",
                    "limit": max_calls,
                    "window_seconds": int(self.window_seconds),
                },
                headers={
                    "Retry-After": str(int(self.window_seconds)),
                    "X-RateLimit-Limit": str(max_calls),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + int(self.window_seconds)),
                },
            )

        response = await call_next(request)

        # Add rate limit headers to successful responses
        if app_settings.rate_limit_include_headers:
            remaining = self._limiter.remaining(key)
            response.headers["X-RateLimit-Limit"] = str(max_calls)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + int(self.window_seconds))

        return response
