"""Watchlist API — manage user's watched symbols with live enriched data."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_current_user, get_watchlist_service
from core.logging import get_logger
from schemas.common.responses import ApiResponse
from services.watchlist_service import WatchlistService

logger = get_logger(__name__)

router = APIRouter()


@router.get("/search", summary="Search symbols", description="Search for symbols to add to watchlist")
async def search_symbols(
    q: str = Query(..., min_length=1, description="Search query (symbol or name)"),
    service: WatchlistService = Depends(get_watchlist_service),
) -> ApiResponse[list[dict[str, Any]]]:
    results = await service.search_symbols(q)
    return ApiResponse[list[dict[str, Any]]](success=True, data=results)


@router.get("/", summary="Watchlist", description="Get watchlist symbols with latest prices")
async def get_watchlist(
    service: WatchlistService = Depends(get_watchlist_service),
) -> ApiResponse[list[dict[str, Any]]]:
    result = await service.list_items()
    return ApiResponse[list[dict[str, Any]]](success=True, data=result.value or [])


@router.post("/", summary="Add symbol", description="Add a symbol to the watchlist")
async def add_symbol(
    body: dict[str, str],
    service: WatchlistService = Depends(get_watchlist_service),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    symbol = body.get("symbol", "").strip()
    name = body.get("name", "")
    if not symbol:
        return ApiResponse[dict[str, Any]](success=False, data={"error": "symbol is required"})
    result = await service.add_symbol(symbol, name)
    if not result.success:
        return ApiResponse[dict[str, Any]](success=False, data={"error": result.error or "خطا در افزودن نماد"})
    return ApiResponse[dict[str, Any]](success=True, data=result.value or {})


@router.delete("/{symbol}", summary="Remove symbol", description="Remove a symbol from the watchlist")
async def remove_symbol(
    symbol: str,
    service: WatchlistService = Depends(get_watchlist_service),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    result = await service.remove_symbol(symbol)
    if not result.success:
        return ApiResponse[dict[str, Any]](success=False, data={"error": f"نماد {symbol} در لیست وجود ندارد"})
    return ApiResponse[dict[str, Any]](success=True, data={"symbol": symbol, "removed": True})
