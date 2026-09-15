"""Health check endpoint. No auth."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    db_ok = False
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.warning("DB health probe failed")

    return {
        "status": "healthy" if db_ok else "degraded",
        "service": "currency_service",
        "version": "0.1.0",
        "db": db_ok,
    }
