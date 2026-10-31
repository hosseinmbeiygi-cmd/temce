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

# ── WebSocket handshake tickets (audit FE-06) ────────────────────────────
# A browser cannot attach an Authorization header to a WebSocket handshake,
# and putting the long-lived access token in the query string leaks it into
# proxy/access logs, browser history and Referer-style tooling. The client
# trades its access token for a single-use, short-lived ticket over
# authenticated HTTP and presents only that ticket in the handshake URL.
_WS_TICKET_PREFIX = "auth:ws_ticket:"
WS_TICKET_TTL_SECONDS = 60


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
    # ``iat`` bounds user-wide revocation (SEC-07): a password change writes a
    # cutoff and every token issued before it is rejected.
    if not to_encode.get("iat"):
        to_encode["iat"] = int(datetime.now(UTC).timestamp())
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
    missing jti or unavailable Redis means "not revoked".

    Security note (fail-open, deliberate): this is an availability-first
    choice. When Redis is down — or the cache circuit breaker is open, or the
    client belongs to a closed event loop and was detached — revocation checks
    are skipped and a revoked token stays usable until it expires
    (``access_token_expire_minutes``, 60 by default). The alternative
    (fail-closed) would lock every user out during a Redis outage. Keep the
    access-token TTL short if that window matters, and treat Redis as part of
    the auth path's availability budget.
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


# A password change must end every session for that user, including access
# tokens that were issued before the change (SEC-07). One Redis marker per user
# holds the cutoff instant; JWTs carry ``iat`` and are rejected when issued
# before it. The TTL equals the access-token lifetime: older tokens have
# already expired on their own.
_USER_REVOKED_PREFIX = "auth:user_revoked:"


def _user_revocation_ttl() -> int:
    return max(60, int(settings.access_token_expire_minutes) * 60 + 60)


async def revoke_user_access_tokens(user_id: str | None) -> bool:
    """Invalidate every access token issued so far for *user_id*.

    Returns ``False`` when the revocation store is unavailable — callers that
    must guarantee it (password change) treat that as a failed operation
    instead of silently leaving the old token valid.
    """
    if not user_id:
        return False
    try:
        from core.cache import get_cache

        cache = get_cache()
        if not cache.is_connected:
            logger.warning("User revocation skipped: Redis unavailable for %s", user_id)
            return False
        await cache.set(
            _USER_REVOKED_PREFIX + str(user_id),
            str(int(datetime.now(UTC).timestamp())),
            ttl=_user_revocation_ttl(),
        )
        return True
    except Exception:  # noqa: BLE001 — never raise from an auth side effect
        logger.debug("User revocation failed for %s", user_id, exc_info=True)
        return False


async def is_user_session_revoked(user_id: str | None, issued_at: Any) -> bool:
    """True when *issued_at* predates the user's last password change.

    Fail-open on an unavailable store, matching the jti blacklist policy
    (availability over strict revocation during a Redis outage); password
    changes refuse to run while the store is down, so the window only opens
    if Redis dies *after* a successful change — bounded by the access TTL.
    """
    if not user_id or issued_at is None:
        return False
    try:
        from core.cache import get_cache

        cache = get_cache()
        if not cache.is_connected:
            return False
        value = await cache.get(_USER_REVOKED_PREFIX + str(user_id))
    except Exception:  # noqa: BLE001
        logger.debug("User revocation check failed for %s", user_id, exc_info=True)
        return False
    if value is None:
        return False
    try:
        cutoff = float(value)
        issued = float(issued_at)
    except (TypeError, ValueError):
        # An unreadable marker is treated as "revoked" (fail-closed on data we
        # cannot interpret, fail-open only on transport).
        return True
    return issued < cutoff


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


def _ws_ticket_key(ticket: str) -> str:
    """Storage key for a ticket — the raw ticket is never written to Redis.

    A Redis snapshot or ``KEYS`` listing then cannot be replayed as a valid
    handshake credential.
    """
    import hashlib

    digest = hashlib.sha256(ticket.encode("utf-8")).hexdigest()
    return _WS_TICKET_PREFIX + digest


async def create_ws_ticket(
    subject: str, *, ttl: int = WS_TICKET_TTL_SECONDS
) -> str | None:
    """Mint a single-use WebSocket ticket, or ``None`` when Redis is down.

    Fail-closed on purpose: a ticket that cannot be persisted cannot be
    verified, and an unverifiable handshake must be rejected rather than
    accepted without authentication. The caller turns ``None`` into a 503.
    """
    import secrets

    from core.cache import get_cache

    cache = get_cache()
    if not cache.is_connected:
        logger.warning("WS ticket not issued: ticket store (Redis) unavailable")
        return None
    ticket = secrets.token_urlsafe(32)
    await cache.set(
        _ws_ticket_key(ticket),
        {"purpose": "ws-handshake", "sub": subject},
        ttl=max(1, ttl),
    )
    return ticket


async def consume_ws_ticket(ticket: str) -> bool:
    """Redeem a ticket exactly once (``GETDEL``); ``False`` for anything else."""
    if not ticket:
        return False
    try:
        from core.cache import get_cache

        cache = get_cache()
        if not cache.is_connected:
            return False
        value = await cache.pop(_ws_ticket_key(ticket))
    except Exception:  # noqa: BLE001 — an unreadable ticket is not a valid one
        logger.debug("WS ticket consume failed", exc_info=True)
        return False
    return isinstance(value, dict) and value.get("purpose") == "ws-handshake"
