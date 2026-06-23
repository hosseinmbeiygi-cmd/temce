from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from apps.api.dependencies import get_market_service
from core.result import PaginatedResult
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


@router.get("/watch", summary="Market watch", description="Get market watch list")
async def market_watch(service: MarketService = Depends(get_market_service)) -> ApiResponse[PaginatedResult[Any]]:
    result = await service.get_market_watch()
    if not result.success:
        return ApiResponse[PaginatedResult[Any]](success=False, data=PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1))
    
    items = result.value
    return ApiResponse[PaginatedResult[Any]](
        success=True,
        data=PaginatedResult(
            items=items,
            total=len(items),
            page=1,
            page_size=len(items),
            total_pages=1,
        )
    )


@router.get("/bourse", summary="Bourse instruments", description="List instruments in the Bourse market")
async def get_bourse(service: MarketService = Depends(get_market_service)) -> ApiResponse[PaginatedResult[Any]]:
    result = await service.get_instruments_by_market("BOURS")
    if not result.success:
        return ApiResponse[PaginatedResult[Any]](success=False, data=PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1))
    
    items = result.value
    return ApiResponse[PaginatedResult[Any]](
        success=True,
        data=PaginatedResult(
            items=[vars(i) for i in items],
            total=len(items),
            page=1,
            page_size=len(items),
            total_pages=1,
        )
    )


@router.get("/energy-commodity", summary="Energy & Commodity", description="List energy and commodity instruments")
async def get_energy_commodity(service: MarketService = Depends(get_market_service)) -> dict[str, Any]:
    result = await service.get_energy_commodity_summary()
    return {
        "success": result.success,
        "summary": result.value.get("summary", {}),
        "sub_markets": result.value.get("sub_markets", [])
    }

