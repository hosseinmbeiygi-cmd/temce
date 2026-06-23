from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.config import settings
from core.exceptions import AuthenticationError


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    import jwt

    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    import jwt

    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        logger.debug("Invalid token", exc_info=True)
        raise AuthenticationError("Invalid token")


def create_refresh_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    import jwt

    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(days=30))
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def decode_refresh_token(token: str) -> dict[str, Any]:
    data = decode_access_token(token)
    if data.get("type") != "refresh":
        raise AuthenticationError("Invalid token type")
    return data
