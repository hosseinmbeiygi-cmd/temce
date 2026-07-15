from __future__ import annotations

import shutil
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

router = APIRouter()


def _status_label(ok: bool, degraded: bool = False) -> str:
    if ok:
        return "ok"
    if degraded:
        return "degraded"
    return "down"


@router.get("", summary="Service health dashboard", description="Real-time health status for all backend services")
async def dashboard_health() -> ApiResponse[dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    degraded_services: list[str] = []
    down_services: list[str] = []

    # ── 1. PostgreSQL ─────────────────────────────────
    db_start = time.monotonic()
    db_ok = False
    try:
        from core.database import async_session_factory

        if async_session_factory is None:
            checks["postgresql"] = {"status": "down", "latency_ms": 0, "detail": "Database not initialised"}
            down_services.append("postgresql")
        else:
            from sqlalchemy import text

            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
            db_ok = True
            latency = round((time.monotonic() - db_start) * 1000, 2)
            checks["postgresql"] = {"status": "ok", "latency_ms": latency, "detail": "Connected"}
    except Exception as exc:
        latency = round((time.monotonic() - db_start) * 1000, 2)
        checks["postgresql"] = {"status": "down", "latency_ms": latency, "detail": str(exc)[:200]}
        down_services.append("postgresql")

    # ── 2. Redis ──────────────────────────────────────
    redis_start = time.monotonic()
    try:
        from core.cache import get_cache

        cache = get_cache()
        if not cache.is_connected:
            checks["redis"] = {"status": "degraded", "latency_ms": 0, "detail": "Not connected – null cache active"}
            degraded_services.append("redis")
        else:
            reachable = await cache.ping()
            latency = round((time.monotonic() - redis_start) * 1000, 2)
            if reachable:
                checks["redis"] = {"status": "ok", "latency_ms": latency, "detail": "Connected"}
            else:
                checks["redis"] = {"status": "down", "latency_ms": latency, "detail": "Ping failed"}
                down_services.append("redis")
    except Exception as exc:
        latency = round((time.monotonic() - redis_start) * 1000, 2)
        checks["redis"] = {"status": "down", "latency_ms": latency, "detail": str(exc)[:200]}
        down_services.append("redis")

    # ── 3. BrsApi ─────────────────────────────────────
    brsapi_start = time.monotonic()
    try:
        from brsapi.client import get_client

        client = await get_client()
        if not client.is_ready:
            checks["brsapi"] = {"status": "degraded", "latency_ms": 0, "detail": "Client not started"}
            degraded_services.append("brsapi")
        else:
            health_info = await client.health()
            latency = round((time.monotonic() - brsapi_start) * 1000, 2)
            reachable = health_info.get("reachable", False)
            if reachable:
                checks["brsapi"] = {"status": "ok", "latency_ms": latency, "detail": "BrsApi.ir reachable"}
            else:
                err = health_info.get("error", "Unknown error")
                checks["brsapi"] = {"status": "degraded", "latency_ms": latency, "detail": err[:200]}
                degraded_services.append("brsapi")
    except Exception as exc:
        latency = round((time.monotonic() - brsapi_start) * 1000, 2)
        checks["brsapi"] = {"status": "down", "latency_ms": latency, "detail": str(exc)[:200]}
        down_services.append("brsapi")

    # ── 4. Disk Space ──────────────────────────────────
    disk_start = time.monotonic()
    try:
        usage = shutil.disk_usage("/")
        total_gb = usage.total // (1024**3)
        used_gb = usage.used // (1024**3)
        free_gb = usage.free // (1024**3)
        used_pct = round(usage.used / usage.total * 100, 1)
        latency = round((time.monotonic() - disk_start) * 1000, 2)

        disk_ok = used_pct < 85
        disk_degraded = 85 <= used_pct < 95

        if not disk_ok and disk_degraded:
            degraded_services.append("disk")
        elif not disk_ok:
            down_services.append("disk")

        checks["disk"] = {
            "status": _status_label(disk_ok, disk_degraded),
            "latency_ms": latency,
            "detail": f"{used_pct}% used",
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "used_pct": used_pct,
        }
    except Exception as exc:
        checks["disk"] = {"status": "degraded", "latency_ms": 0, "detail": f"Check failed: {str(exc)[:100]}"}
        degraded_services.append("disk")

    # ── 5. Uptime / App Info ────────────────────────────
    try:
        from core.config import settings

        app_name = settings.app_name
        app_version = getattr(settings, "app_version", "1.0.0")
    except Exception:
        app_name = "iran-market-platform"
        app_version = "1.0.0"

    # ── Overall status ──────────────────────────────────
    if down_services:
        overall = "down"
    elif degraded_services:
        overall = "degraded"
    else:
        overall = "ok"

    return ApiResponse[dict[str, Any]](
        success=overall != "down",
        data={
            "status": overall,
            "timestamp": datetime.now(UTC).isoformat(),
            "service": app_name,
            "version": app_version,
            "checks": checks,
            "summary": {
                "total": len(checks),
                "ok": sum(1 for c in checks.values() if c.get("status") == "ok"),
                "degraded": len(degraded_services),
                "down": len(down_services),
                "degraded_services": degraded_services,
                "down_services": down_services,
            },
        },
    )
