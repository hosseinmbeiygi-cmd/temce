from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_trade_service
from schemas.common.responses import ApiResponse
from services.trade_service import TradeService

router = APIRouter()


@router.get("/{symbol}", summary="Get trades", description="Get trades for a symbol")
async def get_trades(
    symbol: str,
    limit: int = Query(100, ge=1, le=1000),
    service: TradeService = Depends(get_trade_service),
) -> ApiResponse[list[dict[str, Any]]]:
    result = await service.get_trades(symbol, limit)
    return ApiResponse[list[dict[str, Any]]](success=result.success, data=result.value)


@router.get("/{symbol}/recent", summary="Recent trades", description="Get the most recent trades for a symbol")
async def get_recent_trades(
    symbol: str,
    service: TradeService = Depends(get_trade_service),
) -> ApiResponse[list[dict[str, Any]]]:
    result = await service.get_recent(symbol)
    return ApiResponse[list[dict[str, Any]]](success=result.success, data=result.value)
