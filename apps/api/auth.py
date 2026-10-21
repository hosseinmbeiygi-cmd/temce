from __future__ import annotations

import hmac
import os

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)

_FALSY = {"0", "false", "no", "off", ""}


def _auth_required() -> bool:
    """Whether this process must authenticate requests (API-008).

    Authentication used to be gated on ``is_production``, which made every
    non-production deployment an implicit auth bypass — a staging box reachable
    from the network served the full API with no credentials at all. Being
    *outside* production is no longer a reason to skip auth; the only way to
    turn it off is the explicit ``AUTH_DISABLED`` flag, which the environment
    variable wins over.
    """
    env_val = os.environ.get("AUTH_DISABLED")
    if env_val is not None:
        return env_val.strip().lower() in _FALSY
    return not bool(getattr(settings, "auth_disabled", False))


async def verify_api_key(x_api_key: str = Header("")):
    if _auth_required():
        if not x_api_key or not hmac.compare_digest(x_api_key, settings.secret_key):
            raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


async def verify_token(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    if _auth_required():
        if credentials is None or not credentials.credentials:
            raise HTTPException(status_code=401, detail="Not authenticated")
        token = credentials.credentials
        if len(token) < 8:
            raise HTTPException(status_code=401, detail="Invalid token")
        from core.security.tokens import decode_access_token, is_token_revoked
        try:
            payload = decode_access_token(token)
            if await is_token_revoked(payload.get("jti")):
                raise HTTPException(status_code=401, detail="Token has been revoked")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
    return credentials.credentials if credentials else ""
