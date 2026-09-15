from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_trade_service
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse
from services.trade_service import TradeService

router = APIRouter()


@router.get("/{symbol}", summary="Get trades", description="Get trades for a symbol with pagination")
async def get_trades(
    symbol: str,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0, description="Skip N records for pagination"),
    service: TradeService = Depends(get_trade_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    result = await service.get_trades(symbol, limit + offset)
    all_items = result.value if result.success else []
    items = all_items[offset : offset + limit]
    total = len(all_items)
    total_pages = max(1, (total + limit - 1) // limit) if total else 1
    page = (offset // limit) + 1
    return ApiResponse[PaginatedResult[dict[str, Any]]](
        success=result.success,
        data=PaginatedResult(items=items, total=total, page=page, page_size=limit, total_pages=total_pages),
    )


@router.get("/{symbol}/recent", summary="Recent trades", description="Get the most recent trades for a symbol")
async def get_recent_trades(
    symbol: str,
    service: TradeService = Depends(get_trade_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    result = await service.get_recent(symbol)
    items = result.value if result.success else []
    return ApiResponse[PaginatedResult[dict[str, Any]]](
        success=result.success,
        data=PaginatedResult(items=items, total=len(items), page=1, page_size=20, total_pages=1),
    )
