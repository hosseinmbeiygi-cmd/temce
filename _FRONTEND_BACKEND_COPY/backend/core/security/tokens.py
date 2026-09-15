from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from core.config import settings
from core.exceptions import AuthenticationError
from core.logging import get_logger

logger = get_logger(__name__)

# Redis key prefix for revoked access tokens (by jti).
_REVOKED_PREFIX = "auth:revoked:"


def _new_jti() -> str:
    """Generate a unique JWT ID for the access token."""
    return uuid.uuid4().hex


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    import jwt

    to_encode = data.copy()
    # Add a unique jti claim so individual tokens can be revoked (logout /
    # password change) via a Redis blacklist without invalidating all tokens
    # of the user. Preserves an externally-supplied jti if one is given.
    if not to_encode.get("jti"):
        to_encode["jti"] = _new_jti()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    import jwt

    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        logger.debug("Invalid token", exc_info=True)
        raise AuthenticationError("Invalid token")


def create_refresh_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    import jwt

    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(days=settings.refresh_token_expire_days))
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_refresh_token(token: str) -> dict[str, Any]:
    data = decode_access_token(token)
    if data.get("type") != "refresh":
        raise AuthenticationError("Invalid token type")
    return data


async def is_token_revoked(jti: str | None) -> bool:
    """Return True if the access token with this jti has been revoked.

    Uses Redis when available; in-memory blacklist is not supported, so a
    missing jti or unavailable Redis means "not revoked" (safe default —
    tokens only get revoked when Redis was reachable at logout time).
    """
    if not jti:
        return False
    try:
        from core.cache import get_cache

        cache = get_cache()
        if not cache.is_connected:
            logger.warning("Revocation check skipped: Redis unavailable for jti=%s", jti)
            return False
        value = await cache.get(_REVOKED_PREFIX + jti)
        return value is not None
    except Exception:
        logger.debug("Revocation check failed for jti=%s", jti, exc_info=True)
        return False


async def revoke_token(jti: str | None, ttl: int = 3600) -> None:
    """Revoke an access token by its jti for ``ttl`` seconds (token lifetime).

    No-op when Redis is unavailable — the token cannot be persisted to a
    blacklist. Callers should still clear server-side refresh tokens.
    """
    if not jti:
        return
    try:
        from core.cache import get_cache

        cache = get_cache()
        if not cache.is_connected:
            logger.warning("Revoke skipped: Redis unavailable for jti=%s (ttl=%s)", jti, ttl)
            return
        await cache.set(_REVOKED_PREFIX + jti, "1", ttl=max(1, int(ttl)))
    except Exception:
        logger.debug("Revoke failed for jti=%s", jti, exc_info=True)


async def revoke_access_token(token: str) -> None:
    """Revoke an access token (decode first, then blacklist until its expiry)."""
    try:
        payload = decode_access_token(token)
    except AuthenticationError:
        return
    exp = payload.get("exp")
    ttl = 3600
    if isinstance(exp, (int, float)):
        remaining = float(exp) - datetime.now(UTC).timestamp()
        if remaining > 0:
            ttl = int(remaining) + 60  # small grace window
    await revoke_token(payload.get("jti"), ttl=ttl)
