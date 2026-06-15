from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_market_service
from services.market_service import MarketService

router = APIRouter()


@router.get("/overview")
async def market_overview(service: MarketService = Depends(get_market_service)):
    result = await service.get_overview()
    return {"success": result.success, "data": result.value}


@router.get("/gainers")
async def top_gainers(limit: int = 10, service: MarketService = Depends(get_market_service)):
    result = await service.get_top_gainers(limit)
    return {"success": result.success, "data": result.value}


@router.get("/losers")
async def top_losers(limit: int = 10, service: MarketService = Depends(get_market_service)):
    result = await service.get_top_losers(limit)
    return {"success": result.success, "data": result.value}


@router.get("/active")
async def most_active(limit: int = 10, service: MarketService = Depends(get_market_service)):
    result = await service.get_most_active(limit)
    return {"success": result.success, "data": result.value}
