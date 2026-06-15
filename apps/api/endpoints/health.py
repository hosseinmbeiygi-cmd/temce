from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "iran-market-platform",
    }


@router.get("/ready")
async def readiness():
    return {"status": "ready"}


@router.get("/live")
async def liveness():
    return {"status": "alive"}
