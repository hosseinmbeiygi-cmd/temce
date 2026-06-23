from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_orderbook_service
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse
from services.orderbook_service import OrderBookService

router = APIRouter()


@router.get("/{symbol}", summary="Get orderbook", description="Get current order book for a symbol")
async def get_orderbook(
    symbol: str,
    service: OrderBookService = Depends(get_orderbook_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.get_orderbook(symbol)
    return ApiResponse[dict[str, Any]](success=result.success, data=result.value)


@router.get("/{symbol}/history", summary="Orderbook history", description="Get historical order book snapshots for a symbol")
async def get_orderbook_history(
    symbol: str,
    limit: int = Query(100, ge=1, le=1000),
    service: OrderBookService = Depends(get_orderbook_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    result = await service.get_history(symbol, limit)
    return ApiResponse[PaginatedResult[dict[str, Any]]](success=result.success, data=result.value)
