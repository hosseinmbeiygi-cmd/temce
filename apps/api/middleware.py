from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from contextlib import suppress

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.config import settings as app_settings
from core.logging import get_logger
from core.rate_limit import get_rate_limiter
from core.security.saas import TIERS, get_tier_limiter, tier_subject_from_request
from core.security.sanitizers import strip_html
from core.security.tokens import decode_access_token, is_token_revoked

logger = get_logger(__name__)

# Trace-id header clients can supply to propagate a distributed trace; otherwise
# the server mints a uuid4. Surfaced back on every response as ``X-Trace-Id``.
TRACE_HEADER = "X-Trace-Id"

# Fields whose value is intentionally opaque / hashed server-side (passwords,
# one-time codes, secrets, tokens). Skipping them keeps e.g. ``password``
# with whitespace/symbols intact so the exact-match verification still works.
_SANITIZE_RAW_FIELDS = {
    "password",
    "current_password",
    "new_password",
    "code",
    "secret",
    "token",
    "refresh_token",
    "access_token",
    "mfa_token",
    "telegram_chat_id",
    "api_key",
    "private_key",
}


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
    "/api/v1/watchlist",
    "/api/v1/trades",
    "/api/v1/data-import",
    "/api/v1/signal-insights",
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a per-request context (trace_id, start time) before everything else.

    Must be the OUTERMOST middleware so every downstream layer (logging,
    error handlers, metrics) can read ``request.state.trace_id``.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = request.headers.get(TRACE_HEADER.lower())
        trace_id = incoming or uuid.uuid4().hex
        request.state.trace_id = trace_id
        request.state.request_started = time.monotonic()
        response = await call_next(request)
        response.headers[TRACE_HEADER] = trace_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.monotonic() - start
            trace_id = getattr(request.state, "trace_id", "-")
            logger.exception(
                "Unhandled exception processing %s %s (%.3fs) [trace=%s]",
                request.method,
                request.url.path,
                elapsed,
                trace_id,
            )
            raise
        elapsed = time.monotonic() - start
        trace_id = getattr(request.state, "trace_id", "-")
        logger.info(
            "%s %s -> %d (%.3fs) [trace=%s]",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
            trace_id,
        )
        response.headers["X-Response-Time-Ms"] = str(round(elapsed * 1000))
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = getattr(request.state, "trace_id", "-")
        logger.debug("Request: %s %s [trace=%s]", request.method, request.url.path, trace_id)
        response = await call_next(request)
        logger.debug("Response: %d [trace=%s]", response.status_code, trace_id)
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
                    parts = auth_header.split()
                    if len(parts) != 2 or parts[0].lower() != "bearer":
                        logger.warning("Unauthenticated access to sensitive endpoint: %s %s", request.method, path)
                        return JSONResponse(
                            status_code=401,
                            content={
                                "success": False,
                                "error": "Authentication required for this endpoint",
                                "code": "AUTH_REQUIRED",
                            },
                        )
                    # Validate the token at middleware level (signature + revocation)
                    token = parts[1]
                    try:
                        payload = decode_access_token(token)
                        if payload.get("type") == "refresh":
                            return JSONResponse(
                                status_code=401,
                                content={"success": False, "error": "Invalid token type", "code": "INVALID_TOKEN"},
                            )
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
                        request.method,
                        request.url.path,
                        origin,
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


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Sanitize user-controlled input before it reaches endpoint handlers.

    Applies to request bodies with a JSON content type:
      - Every string field is scanned and cleaned of markup tags and control
        characters (``strip_html`` + stripping of CR/LF/NUL), so ``<script>``
        payloads never reach the database, logs or future render paths.
      - Fields whose value is deliberately opaque — passwords, one-time
        codes, tokens, secrets, chat IDs — are passed through untouched
        (they are hashed/compared byte-for-byte server-side).
      - Non-string values inside string fields are rejected with a 400 so
        type confusion cannot sneak garbage past validation.

    Query/path parameters are sanitized by route-level validation (FastAPI
    types + regex) and are out of scope for a body-level middleware.

    Enabled via ``settings.enable_input_sanitization`` (default True).
    """

    _JSON_CONTENT = ("application/json", "text/json")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not app_settings.enable_input_sanitization:
            return await call_next(request)

        content_type = (request.headers.get("content-type") or "").lower()
        if not content_type.startswith(self._JSON_CONTENT):
            return await call_next(request)

        try:
            raw = await request.body()
            if not raw:
                return await call_next(request)
            payload = json.loads(raw)
        except Exception:
            # Not valid JSON or unreadable — let the normal pipeline handle it.
            return await call_next(request)

        try:
            sanitized = _sanitize_value(payload)
        except _SanitizeTypeError as e:
            logger.warning("Input sanitization rejected %s %s: %s", request.method, request.url.path, e)
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": str(e),
                    "code": "INVALID_INPUT_TYPE",
                },
            )

        # Replace the body the downstream handlers will read.
        body = json.dumps(sanitized, ensure_ascii=False).encode("utf-8")
        request._body = body
        # Keep Content-Length in sync with the sanitized body so ASGI servers
        # don't truncate/over-read the new payload.
        try:
            headers = [(k, v) for k, v in request.scope.get("headers", []) if k.lower() != b"content-length"]
            headers.append((b"content-length", str(len(body)).encode()))
            request.scope["headers"] = headers
            if hasattr(request, "headers"):
                # Starlette caches headers; force rebuild on next access
                with suppress(Exception):
                    request._headers = None  # type: ignore[attr-defined]
        except Exception:
            logger.debug("Failed to update content-length after sanitization", exc_info=True)

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = receive
        return await call_next(request)


class _SanitizeTypeError(ValueError):
    """Raised when a dict field expected to be a string holds another type."""


_MAX_STRING_LEN = 100_000


def _sanitize_value(value, depth: int = 0):
    """Recursively sanitize a parsed JSON body in place (returns new objects)."""
    if depth > 20:
        # Depth guard: strings are still cleaned so a deeply-nested payload
        # cannot smuggle raw markup past the sanitizer.
        if isinstance(value, str):
            return _clean_text(value)[:_MAX_STRING_LEN]
        return value
    if isinstance(value, dict):
        return {k: _sanitize_field(k, v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(v, depth + 1) for v in value]
    if isinstance(value, str):
        # Truncate absurdly long strings before they reach storage.
        if len(value) > _MAX_STRING_LEN:
            value = value[:_MAX_STRING_LEN]
        return _clean_text(value)
    if isinstance(value, (bool, int, float)):
        return value  # non-field scalars (e.g. raw list items) pass through
    return value  # null


def _clean_text(value: str) -> str:
    """Strip markup + control characters (CR/LF/NUL) from a text string."""
    return strip_html(value).replace("\x00", "").replace("\r", "").replace("\n", " ").strip()


def _sanitize_field(key: str, value, depth: int):
    """Sanitize one dict field, honoring the raw (opaque) field allow-list."""
    if isinstance(value, (dict, list)):
        return _sanitize_value(value, depth)
    if isinstance(value, str):
        if key in _SANITIZE_RAW_FIELDS:
            # Opaque field: cap length, drop NUL bytes, but keep everything else.
            return value[:_MAX_STRING_LEN].replace("\x00", "")
        if len(value) > _MAX_STRING_LEN:
            value = value[:_MAX_STRING_LEN]
        return _clean_text(value)
    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        return value  # numbers/booleans are legitimate JSON payloads
    # Any other type in a scalar field — reject so type confusion surfaces
    # as a clear 400 instead of silently coercing.
    raise _SanitizeTypeError(f"Field '{key}' must be a string")


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

        allowed, remaining = await self._limiter.allow_async(
            key,
            max_calls=max_calls,
            window_seconds=self.window_seconds,
        )

        # ── Tier layer (منشور بخش ۴): per-user token bucket on top of the
        # per-IP sliding window. Authenticated users get their tier's bucket
        # (free/pro/institutional); anonymous requests fall through to the
        # IP window untouched.
        tier_remaining: int | None = None
        tier_limit: int | None = None
        subject = tier_subject_from_request(request)
        if subject is not None:
            tier_name = subject.split(":", 1)[0]
            tier = TIERS[tier_name]
            tier_limiter = get_tier_limiter()
            if not tier_limiter.allow(subject, tier):
                logger.warning(
                    "Tier limit exceeded: %s %s subject=%s tier=%s (burst=%d)",
                    request.method,
                    path,
                    subject,
                    tier.name,
                    tier.burst,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": "Tier rate limit exceeded",
                        "code": "TIER_RATE_LIMIT",
                        "tier": tier.name,
                        "limit": tier.burst,
                        "window_seconds": round(tier.refill_seconds, 3),
                    },
                    headers={
                        "Retry-After": str(max(1, int(tier.refill_seconds + 0.999))),
                        "X-RateLimit-Limit": str(tier.burst),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + max(1, int(tier.refill_seconds + 0.999))),
                    },
                )
            tier_remaining = tier_limiter.remaining(subject, tier)
            tier_limit = tier.burst

        if not allowed:
            logger.warning(
                "Rate limit exceeded: %s %s from %s (limit: %d/min)", request.method, path, client_ip, max_calls
            )
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
            response.headers["X-RateLimit-Limit"] = str(tier_limit if tier_limit is not None else max_calls)
            response.headers["X-RateLimit-Remaining"] = str(
                tier_remaining if tier_remaining is not None else remaining
            )
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + int(self.window_seconds))

        return response
