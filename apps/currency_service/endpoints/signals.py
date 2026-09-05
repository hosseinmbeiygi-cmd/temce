"""GET /currency/signals — current signals only (served from the overview cache)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from apps.currency_service.config import settings
from apps.currency_service.endpoints.overview import _compute_overview
from apps.currency_service.infra.cache import cached_overview

router = APIRouter()


@router.get("/signals")
async def signals() -> dict[str, Any]:
    full = await cached_overview(_compute_overview, ttl=settings.cache_ttl_seconds)
    return {
        "timestamp": full["timestamp"],
        "kill_switch_active": full["kill_switch"]["active"],
        "count": len(full["signals"]),
        "signals": full["signals"],
    }