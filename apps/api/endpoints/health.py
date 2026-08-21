from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)
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
async def readiness() -> JSONResponse:
    """Report whether required runtime dependencies can serve requests.

    Liveness only answers whether the process is alive. Readiness verifies the
    database and Redis cache separately and returns HTTP 503 while either
    dependency is unavailable, so a load balancer will stop sending traffic.
    """
    checks: dict[str, dict[str, Any]] = {}

    try:
        from sqlalchemy import text

        from core.database import async_session_factory

        if async_session_factory is None:
            raise RuntimeError("database is not initialized")
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception:
        logger.exception("Readiness database check failed")
        checks["database"] = {"status": "error", "detail": "database unavailable"}

    try:
        from core.cache import get_cache

        cache = get_cache()
        if not cache.is_connected or not await cache.ping():
            raise RuntimeError("Redis is unavailable")
        checks["redis"] = {"status": "ok"}
    except Exception:
        logger.exception("Readiness Redis check failed")
        checks["redis"] = {"status": "error", "detail": "redis unavailable"}

    ready = all(check["status"] == "ok" for check in checks.values())
    body = ApiResponse[dict[str, Any]](
        success=ready,
        data={
            "status": "ready" if ready else "not_ready",
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": checks,
        },
        error=None if ready else {"message": "One or more required dependencies are unavailable"},
    )
    return JSONResponse(status_code=200 if ready else 503, content=body.model_dump())


@router.get("/live", summary="Liveness check", description="Liveness probe for orchestration")
async def liveness() -> ApiResponse[dict[str, str]]:
    return ApiResponse[dict[str, str]](success=True, data={"status": "alive"})


@router.get("/full", summary="Full health check", description="Check status of all backend services: database, cache (Redis), and BrsAPI")
async def full_health() -> ApiResponse[dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    overall = "ok"

    # ── Database check ───────────────────────────────
    db_start = time.monotonic()
    try:
        from core.database import async_session_factory

        if async_session_factory is None:
            db_status, db_detail = "down", "Database not initialised"
        else:
            async with async_session_factory() as session:
                from sqlalchemy import text
                await session.execute(text("SELECT 1"))
            db_status, db_detail = "ok", "PostgreSQL connected"
    except Exception:
        logger.exception("Full health database check failed")
        db_status, db_detail = "error", "database unavailable"
    checks["database"] = {
        "status": db_status,
        "latency_ms": round((time.monotonic() - db_start) * 1000, 2),
        "detail": db_detail,
    }
    if db_status != "ok":
        overall = "degraded"

    # ── Redis / Cache check ──────────────────────────
    cache_start = time.monotonic()
    try:
        from core.cache import get_cache

        cache = get_cache()
        if not cache.is_connected:
            cache_status, cache_detail = "unavailable", "Redis not connected – using null cache"
        else:
            reachable = await cache.ping()
            cache_status, cache_detail = ("ok", "Redis connected") if reachable else ("unavailable", "Redis ping failed")
    except Exception:
        logger.exception("Full health Redis check failed")
        cache_status, cache_detail = "error", "redis unavailable"
    checks["redis"] = {
        "status": cache_status,
        "latency_ms": round((time.monotonic() - cache_start) * 1000, 2),
        "detail": cache_detail,
    }

    # ── BrsAPI check ─────────────────────────────────
    brsapi_start = time.monotonic()
    try:
        from brsapi.client import get_client

        client = await get_client()
        if not client.is_ready:
            brsapi_status, brsapi_detail = "down", "BrsApiClient not started"
        else:
            health_info = await client.health()
            if health_info.get("reachable"):
                brsapi_status, brsapi_detail = "ok", "BrsApi.ir reachable"
            else:
                brsapi_status, brsapi_detail = "error", health_info.get("error", "Unknown BrsAPI error")
    except Exception:
        logger.exception("Full health BrsApi check failed")
        brsapi_status, brsapi_detail = "error", "BrsApi unavailable"
    checks["brsapi"] = {
        "status": brsapi_status,
        "latency_ms": round((time.monotonic() - brsapi_start) * 1000, 2),
        "detail": brsapi_detail,
    }

    return ApiResponse[dict[str, Any]](
        success=overall == "ok",
        data={
            "status": overall,
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": checks,
        },
    )
