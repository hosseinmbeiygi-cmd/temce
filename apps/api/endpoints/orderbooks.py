from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_orderbook_service
from services.orderbook_service import OrderBookService

router = APIRouter()


@router.get("/{symbol}")
async def get_orderbook(symbol: str, service: OrderBookService = Depends(get_orderbook_service)):
    result = await service.get_orderbook(symbol)
    return {"success": result.success, "data": result.value}


@router.get("/{symbol}/history")
async def get_orderbook_history(
    symbol: str, limit: int = 100, service: OrderBookService = Depends(get_orderbook_service)
):
    result = await service.get_history(symbol, limit)
    return {"success": result.success, "data": result.value}
