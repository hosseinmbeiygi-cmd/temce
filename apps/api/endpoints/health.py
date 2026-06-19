from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from schemas.common.responses import ApiResponse

router = APIRouter()


@router.get("", summary="Health check", description="Basic health check endpoint")
async def health_check() -> ApiResponse[dict[str, str]]:
    return ApiResponse[dict[str, str]](
        success=True,
        data={
            "status": "ok",
            "timestamp": datetime.now(UTC).isoformat(),
            "service": "iran-market-platform",
        },
    )


@router.get("/ready", summary="Readiness check", description="Readiness probe for orchestration")
async def readiness() -> ApiResponse[dict[str, str]]:
    return ApiResponse[dict[str, str]](success=True, data={"status": "ready"})


@router.get("/live", summary="Liveness check", description="Liveness probe for orchestration")
async def liveness() -> ApiResponse[dict[str, str]]:
    return ApiResponse[dict[str, str]](success=True, data={"status": "alive"})
