from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends

from apps.api.dependencies import get_analytics_service
from schemas.common.responses import ApiResponse
from services.analytics_service import AnalyticsService

router = APIRouter()


@router.post(
    "/{instrument_id}/{name}", summary="Create indicator", description="Create a technical indicator for an instrument"
)
async def create_indicator(
    instrument_id: str,
    name: str,
    body: dict[str, Any] = Body(...),
    service: AnalyticsService = Depends(get_analytics_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.create(instrument_id=instrument_id, name=name, **body)
    return ApiResponse[dict[str, Any]](
        success=result.success,
        data=result.value,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get(
    "/{instrument_id}/{name}", summary="Get indicator", description="Get a technical indicator value for an instrument"
)
async def get_indicator(
    instrument_id: str,
    name: str,
    timeframe: str = "1d",
    service: AnalyticsService = Depends(get_analytics_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.get_indicator(instrument_id, name, timeframe)
    return ApiResponse[dict[str, Any]](success=result.success, data=result.value)
