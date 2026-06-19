from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_market_service
from schemas.common.responses import ApiResponse
from services.market_service import MarketService

router = APIRouter()


@router.get("/overview", summary="Market overview", description="Get overall market summary including indices and sector performance")
async def market_overview(service: MarketService = Depends(get_market_service)) -> ApiResponse[dict[str, Any]]:
    result = await service.get_overview()
    return ApiResponse[dict[str, Any]](success=result.success, data=result.value)


@router.get("/gainers", summary="Top gainers", description="Get top gaining symbols")
async def top_gainers(
    limit: int = Query(10, ge=1, le=100),
    service: MarketService = Depends(get_market_service),
) -> ApiResponse[Any]:
    result = await service.get_top_gainers(limit)
    return ApiResponse[Any](success=result.success, data=result.value)


@router.get("/losers", summary="Top losers", description="Get top losing symbols")
async def top_losers(
    limit: int = Query(10, ge=1, le=100),
    service: MarketService = Depends(get_market_service),
) -> ApiResponse[Any]:
    result = await service.get_top_losers(limit)
    return ApiResponse[Any](success=result.success, data=result.value)


@router.get("/active", summary="Most active", description="Get most actively traded symbols")
async def most_active(
    limit: int = Query(10, ge=1, le=100),
    service: MarketService = Depends(get_market_service),
) -> ApiResponse[Any]:
    result = await service.get_most_active(limit)
    return ApiResponse[Any](success=result.success, data=result.value)
