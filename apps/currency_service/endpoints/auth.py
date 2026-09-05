"""User resolution for the currency service.

Accepts the platform JWT (Bearer) issued by apps/api — verified with the
shared ``settings.secret_key`` — or an ``X-User-Id`` header for local dev
and curl. First identity wins; missing/invalid → 401.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from core.logging import get_logger
from core.security.tokens import decode_access_token

logger = get_logger(__name__)


async def resolve_user(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            claims = decode_access_token(token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            ) from None
        sub = claims.get("sub") or claims.get("user_id")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has no user identity",
            )
        return str(sub)

    if x_user_id and x_user_id.strip():
        return x_user_id.strip()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Bearer token or X-User-Id header required",
    )