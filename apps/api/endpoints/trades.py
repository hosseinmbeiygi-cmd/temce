from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_trade_service
from services.trade_service import TradeService

router = APIRouter()


@router.get("/{symbol}")
async def get_trades(symbol: str, limit: int = 100, service: TradeService = Depends(get_trade_service)):
    result = await service.get_trades(symbol, limit)
    return {"success": result.success, "data": result.value}


@router.get("/{symbol}/recent")
async def get_recent_trades(symbol: str, service: TradeService = Depends(get_trade_service)):
    result = await service.get_recent(symbol)
    return {"success": result.success, "data": result.value}
