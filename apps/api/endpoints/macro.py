from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_macro_service
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse
from services.macro_service import MacroService

router = APIRouter()


@router.get("/", summary="List indicators", description="List all available macro indicators")
async def list_indicators(
    service: MacroService = Depends(get_macro_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    result = await service.list_indicators()
    if not result.success:
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=False,
            data=PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1),
        )
    items = [{"key": k} for k in result.value]
    return ApiResponse[PaginatedResult[dict[str, Any]]](
        success=True,
        data=PaginatedResult(items=items, total=len(items), page=1, page_size=len(items), total_pages=1),
    )


@router.get("/{indicator}", summary="Get indicator", description="Get current value of a macro indicator")
async def get_indicator(
    indicator: str,
    service: MacroService = Depends(get_macro_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.get_indicator(indicator)
    return ApiResponse[dict[str, Any]](success=result.success, data=result.value)


@router.get("/{indicator}/history", summary="Indicator history", description="Get historical values of a macro indicator")
async def get_indicator_history(
    indicator: str,
    limit: int = Query(100, ge=1, le=1000),
    service: MacroService = Depends(get_macro_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    result = await service.get_history(indicator, limit)
    if not result.success:
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=False,
            data=PaginatedResult(items=[], total=0, page=1, page_size=limit, total_pages=1),
        )
    items = result.value if isinstance(result.value, list) else []
    return ApiResponse[PaginatedResult[dict[str, Any]]](
        success=True,
        data=PaginatedResult(items=items, total=len(items), page=1, page_size=limit, total_pages=1),
    )
