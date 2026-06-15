from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)


async def verify_api_key(x_api_key: str = Header("")):
    if settings.is_production and x_api_key != settings.secret_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


async def verify_token(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    if settings.is_production:
        if credentials is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        token = credentials.credentials
        if not token or len(token) < 8:
            raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials if credentials else ""
