from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from apps.api.dependencies import get_symbol_service
from schemas.common.responses import ApiResponse
from services.symbol_service import SymbolService

router = APIRouter()


@router.post("", summary="Create symbol", description="Create a new trading symbol/instrument")
async def create_symbol(
    body: dict[str, Any] = Body(...),
    service: SymbolService = Depends(get_symbol_service),
) -> ApiResponse[dict[str, Any]]:
    rest = {k: v for k, v in body.items() if k not in ("symbol", "name")}
    result = await service.create(symbol=body.get("symbol", ""), name=body.get("name", ""), **rest)
    return ApiResponse[dict[str, Any]](
        success=result.success,
        data=result.value,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get("", summary="List symbols", description="List all trading symbols with pagination")
async def list_symbols(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    service: SymbolService = Depends(get_symbol_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.list_all(page, page_size)
    return ApiResponse[dict[str, Any]](success=result.success, data=result.value)


@router.get("/search", summary="Search symbols", description="Search symbols by name or symbol code")
async def search_symbols(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    service: SymbolService = Depends(get_symbol_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.search(q, page)
    return ApiResponse[dict[str, Any]](success=result.success, data=result.value)


@router.get("/{symbol}", summary="Get symbol", description="Get a single symbol by its code")
async def get_symbol(
    symbol: str,
    service: SymbolService = Depends(get_symbol_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.get_by_symbol(symbol)
    return ApiResponse[dict[str, Any]](
        success=result.success,
        data=result.value,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get("/{symbol}/detail", summary="Symbol detail", description="Get detailed information about a symbol")
async def get_symbol_detail(
    symbol: str,
    service: SymbolService = Depends(get_symbol_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.get_detail(symbol)
    return ApiResponse[dict[str, Any]](
        success=result.success,
        data=result.value,
        error={"message": result.error} if not result.success and result.error else None,
    )
