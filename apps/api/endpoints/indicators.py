from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends

from apps.api.dependencies import get_analytics_service
from services.analytics_service import AnalyticsService

router = APIRouter()


@router.post("/{instrument_id}/{name}")
async def create_indicator(
    instrument_id: str,
    name: str,
    body: dict[str, Any] = Body(...),
    service: AnalyticsService = Depends(get_analytics_service),
):
    result = await service.create(instrument_id=instrument_id, name=name, **body)
    return {"success": result.success, "data": result.value, "error": result.error if not result.success else None}


@router.get("/{instrument_id}/{name}")
async def get_indicator(
    instrument_id: str, name: str, timeframe: str = "1d", service: AnalyticsService = Depends(get_analytics_service)
):
    result = await service.get_indicator(instrument_id, name, timeframe)
    return {"success": result.success, "data": result.value}
