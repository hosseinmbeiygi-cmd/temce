"""Auth & RBAC صندوق‌یار — مطابق شکاف ۵ spec.

نقش‌ها:
- guest: /funds و /funds/{symbol} فقط خواندنی
- user: تمام GET ها + /alerts شخصی
- analyst: + /screener پیشرفته + /backtest/report
- admin: همه + مدیریت config و وزن‌ها

Rate Limiting (Redis-backed): guest 60/min/IP, user 300/min, analyst 600/min.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.time import now_utc

from .constants import SIGNAL_LABELS_FA  # noqa: F401 (برای دسترسی ساده‌تر)

security = HTTPBearer(auto_error=False)

# ── نقش‌ها و دسترسی ─────────────────────────────────────────────────
ROLE_GUEST = "guest"
ROLE_USER = "user"
ROLE_ANALYST = "analyst"
ROLE_ADMIN = "admin"

ROLES = (ROLE_GUEST, ROLE_USER, ROLE_ANALYST, ROLE_ADMIN)

# هر نقش چه مسیرهایی می‌تواند ببیند
ROLE_PERMISSIONS: dict[str, set[str]] = {
    ROLE_GUEST: {"funds:read", "funds:profile"},
    ROLE_USER: {"funds:read", "funds:profile", "alerts:read", "alerts:write", "funds:compare"},
    ROLE_ANALYST: {
        "funds:read",
        "funds:profile",
        "funds:compare",
        "screener",
        "backtest:report",
        "alerts:read",
        "alerts:write",
    },
    ROLE_ADMIN: {"*"},
}

RATE_LIMITS_PER_MINUTE: dict[str, int] = {
    ROLE_GUEST: 60,
    ROLE_USER: 300,
    ROLE_ANALYST: 600,
    ROLE_ADMIN: 1200,
}


@dataclass
class UserContext:
    sub: str
    role: str = ROLE_GUEST
    scopes: set[str] = field(default_factory=set)

    def has_scope(self, scope: str) -> bool:
        if "*" in self.scopes:
            return True
        return scope in self.scopes


# ── Issue و Verify توکن (RS256 به‌صورت ساده برای dev) ───────────────
def issue_token(sub: str, role: str, *, ttl_minutes: int = 15) -> str:
    """ساخت JWT-like توکن برای dev/test.

    در تولید: باید از RS256 با کلید خصوصی استفاده شود (پیمایش spec).
    """
    import json

    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
        "jti": secrets.token_hex(8),
    }
    header = {"alg": "HS256", "typ": "JWT"}

    def _b64(data: bytes) -> str:
        return __import__("base64").urlsafe_b64encode(data).rstrip(b"=").decode()

    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(payload).encode())}"
    secret = _DEV_SECRET
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).hexdigest()
    return f"{signing_input}.{signature}"


_DEV_SECRET = os.environ.get("SANDOOGHYAR_JWT_SECRET") or secrets.token_hex(32)


def verify_token(token: str) -> UserContext | None:
    """اعتبارسنجی توکن — خروجی None برای نامعتبر/منقضی."""
    import json

    parts = token.split(".")
    if len(parts) != 3:
        return None
    signing_input, signature = f"{parts[0]}.{parts[1]}", parts[2]

    def _b64d(s: str) -> bytes:
        pad = "=" * (-len(s) % 4)
        return __import__("base64").urlsafe_b64decode(s + pad)

    expected = hmac.new(_DEV_SECRET.encode(), signing_input.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        payload = json.loads(_b64d(parts[1]))
    except Exception:
        return None

    if payload.get("exp", 0) < int(datetime.now(UTC).timestamp()):
        return None

    role = payload.get("role", ROLE_GUEST)
    return UserContext(
        sub=payload.get("sub", "unknown"),
        role=role if role in ROLES else ROLE_GUEST,
        scopes=ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS[ROLE_GUEST]),
    )


# ── API Key ──────────────────────────────────────────────────────────
def generate_api_key(env: str = "dev") -> str:
    """فرمت: syar_{env}_{32 hex} — اصل کلید فقط یک‌بار نمایش داده می‌شود."""
    return f"syar_{env}_{secrets.token_hex(16)}"


def hash_api_key(api_key: str) -> str:
    """هش SHA-256 برای ذخیره در DB."""
    return hashlib.sha256(api_key.encode()).hexdigest()


# ── Dependencies برای FastAPI ────────────────────────────────────────
async def get_user_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_api_key: str | None = Header(default=None),
) -> UserContext:
    if x_api_key:
        # در تولید: جستجوی هش در DB
        role = ROLE_ANALYST if x_api_key.startswith("syar_") else ROLE_GUEST
        return UserContext(sub=f"apikey:{hash_api_key(x_api_key)[:16]}", role=role, scopes=ROLE_PERMISSIONS[role])
    if credentials and credentials.credentials:
        ctx = verify_token(credentials.credentials)
        if ctx is not None:
            return ctx
    return UserContext(sub="guest", role=ROLE_GUEST, scopes=ROLE_PERMISSIONS[ROLE_GUEST])


async def require_role(*roles: str):
    async def _dep(user: UserContext = Depends(get_user_context)) -> UserContext:
        if user.role not in roles and user.role != ROLE_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(roles)}",
            )
        return user

    return _dep


def require_permission(scope: str):
    """Dependency — بررسی دسترسی بر اساس scope."""

    async def _dep(user: UserContext = Depends(get_user_context)) -> UserContext:
        if not user.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {scope}",
            )
        return user

    return _dep


# ── Rate Limiter (Redis-backed) ──────────────────────────────────────
class RateLimiter:
    """Rate Limiter ساده — in-memory برای dev، Redis در تولید.

    الگوریتم: Fixed Window با شمارنده per key.
    """

    def __init__(self):
        self._buckets: dict[str, tuple[int, datetime]] = {}
        self.redis = None

    def check(self, key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        """بررسی اینکه آیا key از limit در window رد شده.

        Returns: (allowed, remaining)
        """
        now = now_utc()
        count, start = self._buckets.get(key, (0, now))
        if (now - start).total_seconds() > window_seconds:
            count, start = 0, now
        remaining = max(0, limit - count)
        if count >= limit:
            return False, 0
        self._buckets[key] = (count + 1, start)
        return True, remaining

    def retry_after(self, key: str) -> int:
        _, start = self._buckets.get(key, (0, now_utc()))
        return max(0, 60 - int((now_utc() - start).total_seconds()))


rate_limiter = RateLimiter()


async def rate_limit_dependency(request: Request, user: UserContext = Depends(get_user_context)):
    """Dependency — اعمال Rate Limit بر اساس نقش."""
    limit = RATE_LIMITS_PER_MINUTE.get(user.role, 60)
    key = user.sub if user.role != ROLE_GUEST else request.client.host if request.client else "guest"
    allowed, remaining = rate_limiter.check(key, limit)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limit_exceeded",
            headers={"Retry-After": str(rate_limiter.retry_after(key))},
        )
    return user
