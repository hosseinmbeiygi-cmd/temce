"""SaaS monetization primitives: tiered token buckets + scoped API tokens.

منشور بخش ۴:
  * Free / Pro / Institutional tiers, each with its own token-bucket
    (requests-per-minute and burst) enforced per user/key — layered ON TOP of
    the per-IP sliding window in ``apps/api/middleware.py``.
  * Scoped API tokens (``gdesk_...``) for the GoldDesk analysis environment:
    every token carries a tier, an explicit scope list and an owner. HTTP
    surface: 401 without/with-bad key, 403 with insufficient scope.

No Redis/DB dependency: pure in-process state with a test-controllable clock,
so unit tests are deterministic. The per-user limiter composes with the
existing Redis sliding window (allow_async) at the middleware layer.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time as _time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request
from fastapi.security.utils import get_authorization_scheme_param

from core.logging import get_logger
from core.rate_limit.tokens import TokenBucket

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Tier catalog
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Tier:
    name: str
    rpm: int            # sustained requests-per-minute
    burst: int          # bucket capacity (immediate burst allowance)
    daily_quota: int    # optional hard daily cap (0 = unlimited)

    @property
    def refill_seconds(self) -> float:
        """Seconds for ONE token to refill (60 / rpm)."""
        return 60.0 / self.rpm


TIERS: dict[str, Tier] = {
    "free": Tier(name="free", rpm=10, burst=10, daily_quota=1_000),
    "pro": Tier(name="pro", rpm=120, burst=120, daily_quota=50_000),
    "institutional": Tier(name="institutional", rpm=600, burst=600, daily_quota=0),
}

# JWT roles → tier mapping (resolve_tier picks the highest tier present).
_ROLE_TO_TIER: dict[str, str] = {
    "admin": "institutional",
    "institutional": "institutional",
    "pro": "pro",
    "user": "free",
}


def resolve_tier(roles: list[str] | None) -> str:
    """Resolve the highest tier implied by a JWT role list (default: free)."""
    if not roles:
        return "free"
    best = "free"
    for role in roles:
        tier_name = _ROLE_TO_TIER.get(str(role).lower())
        if tier_name is not None and TIERS[tier_name].rpm > TIERS[best].rpm:
            best = tier_name
    return best


# ─────────────────────────────────────────────────────────────────────
# Per-user token-bucket limiter
# ─────────────────────────────────────────────────────────────────────


class TieredTokenBucketLimiter:
    """Per-subject token buckets keyed by ``(subject, tier)``.

    In-process by design: the Redis sliding window (RateLimitMiddleware)
    already aggregates cross-worker; these buckets enforce the per-user
    tier shape locally in every worker. The clock offset is shared across
    all buckets so tests advance time deterministically.
    """

    def __init__(self, max_subjects: int = 100_000) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self._clock_offset = 0.0
        self._max_subjects = max_subjects

    def advance_time(self, seconds: float) -> None:
        """Advance every bucket's clock (test determinism)."""
        self._clock_offset += seconds
        for bucket in self._buckets.values():
            bucket.advance_time(seconds)

    def _bucket(self, subject: str, tier: Tier) -> TokenBucket:
        key = f"{subject}:{tier.name}"
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self._max_subjects:
                self._evict_full_buckets()
            bucket = TokenBucket(rate=1.0 / tier.refill_seconds, burst=tier.burst)
            # Inherit the limiter's clock so advance_time() reaches all buckets.
            bucket._clock_offset = self._clock_offset
            self._buckets[key] = bucket
        return bucket

    def _evict_full_buckets(self) -> None:
        full = [k for k, b in self._buckets.items() if b.available_sync >= b.burst]
        for k in full:
            del self._buckets[k]
        # Extreme adversarial load: drop the oldest half regardless of state.
        if len(self._buckets) >= self._max_subjects:
            for k in list(self._buckets)[: len(self._buckets) // 2]:
                del self._buckets[k]

    def allow(self, subject: str, tier: Tier) -> bool:
        """Try to consume one token for ``subject`` under ``tier`` limits."""
        return self._bucket(subject, tier).try_acquire_sync()

    def remaining(self, subject: str, tier: Tier) -> int:
        return int(self._bucket(subject, tier).available_sync)


_global_tier_limiter = TieredTokenBucketLimiter()


def get_tier_limiter() -> TieredTokenBucketLimiter:
    return _global_tier_limiter


# ─────────────────────────────────────────────────────────────────────
# Scoped API tokens (GoldDesk)
# ─────────────────────────────────────────────────────────────────────

# Scopes are ``<domain>:<access>`` pairs.
SCOPES: frozenset[str] = frozenset(
    {
        "market:read",
        "market:read_extended",
        "options:read",
        "options:analyze",
        "portfolio:read",
        "portfolio:write",
        "signals:read",
        "signals:generate",
        "gold:read",
        "gold:analyze",
        "admin:write",
    }
)


@dataclass(frozen=True)
class ScopedToken:
    tier: str
    scopes: tuple[str, ...]
    owner: str
    token_id: str
    expires_at: float


_SECRET: bytes = b""


def _secret() -> bytes:
    """Process-wide signing secret derived from the configured secret key."""
    global _SECRET
    if not _SECRET:
        from core.config import settings

        _SECRET = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return _SECRET


def _sign(body: str) -> str:
    return hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()[:32]


def create_scoped_token(
    tier: str,
    scopes: list[str],
    owner: str,
    ttl_days: float = 365.0,
    token_id: str | None = None,
) -> str:
    """Create a ``gdesk_...`` scoped API key and return it in full (once)."""
    if tier not in TIERS:
        raise ValueError(f"unknown tier: {tier!r} (valid: {sorted(TIERS)})")
    unknown = set(scopes) - SCOPES
    if unknown:
        raise ValueError(f"unknown scopes: {sorted(unknown)} (valid: {sorted(SCOPES)})")
    if not owner.strip():
        raise ValueError("owner must not be empty")

    payload = {
        "t": tier,
        "s": sorted(scopes),
        "o": owner,
        "id": token_id or secrets.token_hex(8),
        "exp": _time.time() + ttl_days * 86_400.0,
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    body_str = body.decode("ascii").rstrip("=")
    return f"gdesk_{body_str}_{_sign(body_str)}"


def verify_scoped_token(raw: str) -> ScopedToken:
    """Verify signature/expiry and return the parsed token claims."""
    if not raw.startswith("gdesk_"):
        raise ScopedTokenError("malformed token: missing gdesk_ prefix")
    body, sep, sig = raw[len("gdesk_") :].rpartition("_")
    if not sep or not body or not sig:
        raise ScopedTokenError("malformed token: missing signature segment")
    if not hmac.compare_digest(_sign(body), sig):
        raise ScopedTokenError("invalid token signature")
    try:
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ScopedTokenError("malformed token body") from exc
    if float(payload.get("exp", 0)) < _time.time():
        raise ScopedTokenError("token expired")
    tier = str(payload.get("t", ""))
    scopes = tuple(str(s) for s in payload.get("s", []))
    unknown = set(scopes) - SCOPES
    if tier not in TIERS or unknown:
        raise ScopedTokenError("token references unknown tier or scope")
    return ScopedToken(
        tier=tier,
        scopes=scopes,
        owner=str(payload.get("o", "")),
        token_id=str(payload.get("id", "")),
        expires_at=float(payload.get("exp", 0.0)),
    )


class ScopedTokenError(Exception):
    """Raised when a scoped token fails verification."""


def require_scopes(*required: str) -> Callable[[ScopedToken], ScopedToken]:
    """Build a checker enforcing that a token carries ALL required scopes."""

    def checker(token: ScopedToken) -> ScopedToken:
        missing = [s for s in required if s not in token.scopes]
        if missing:
            raise HTTPException(status_code=403, detail=f"insufficient scope: {missing}")
        return token

    return checker


# ─────────────────────────────────────────────────────────────────────
# HTTP surface (FastAPI)
# ─────────────────────────────────────────────────────────────────────


def api_key_auth(*required_scopes: str) -> Any:
    """FastAPI dependency factory: verify ``X-API-Key`` and enforce scopes.

    Usage::

        @router.get("/gold/snapshot", dependencies=[Depends(api_key_auth("gold:read"))])
        async def snapshot(): ...
    """

    async def dependency(request: Request) -> ScopedToken:
        raw = request.headers.get("X-API-Key", "")
        if not raw:
            raise HTTPException(status_code=401, detail="missing API key")
        try:
            token = verify_scoped_token(raw)
        except ScopedTokenError as exc:
            raise HTTPException(status_code=401, detail=f"invalid API key: {exc}") from exc
        # Scoped tokens carry their own tier — enforce the per-token bucket so
        # gdesk API keys cannot bypass the per-user tier shape (منشور بخش ۴).
        tier = TIERS[token.tier]
        if not get_tier_limiter().allow(f"gdesk:{token.token_id}", tier):
            retry_after = max(1, int(tier.refill_seconds + 0.999))
            raise HTTPException(
                status_code=429,
                detail="tier rate limit exceeded",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(tier.burst),
                    "X-RateLimit-Remaining": "0",
                },
            )
        if required_scopes:
            require_scopes(*required_scopes)(token)
        return token

    return dependency


# ─────────────────────────────────────────────────────────────────────
# JWT role → tier bridge (per-user bucket in middleware)
# ─────────────────────────────────────────────────────────────────────


def tier_subject_from_request(request: Request) -> str | None:
    """Extract a stable per-user subject from the bearer JWT, if any.

    Returns None for anonymous requests (no Authorization header) — those are
    handled by the existing per-IP sliding window only.
    """
    scheme, param = get_authorization_scheme_param(request.headers.get("authorization", ""))
    if scheme.lower() != "bearer" or not param:
        return None
    try:
        from core.security.tokens import decode_access_token

        payload = decode_access_token(param)
    except Exception:  # noqa: BLE001 — anonymous fallback must never raise
        return None
    sub = str(payload.get("sub", ""))
    if not sub:
        return None
    roles = payload.get("roles") or []
    tier_name = resolve_tier(list(roles) if isinstance(roles, list) else [])
    return f"{tier_name}:{sub}"


__all__ = [
    "SCOPES",
    "ScopedToken",
    "ScopedTokenError",
    "TIERS",
    "Tier",
    "TieredTokenBucketLimiter",
    "api_key_auth",
    "create_scoped_token",
    "get_tier_limiter",
    "require_scopes",
    "resolve_tier",
    "tier_subject_from_request",
    "verify_scoped_token",
]
