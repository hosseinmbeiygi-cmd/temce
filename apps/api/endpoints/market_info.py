from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from apps.api.dependencies import get_brsapi_query_service, get_symbol_service
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse
from services.symbol_service import SymbolService

router = APIRouter()


@router.get("/industries", summary="List industries", description="List all industries sorted by count")
async def list_industries(
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    try:
        categories = await brsapi.get_commodity_categories()
        items = sorted(
            [{"name": cat.get("category", "سایر"), "count": cat.get("count", 0), "last_update": cat.get("last_update", "")}
             for cat in categories],
            key=lambda x: x["count"],
            reverse=True,
        ) if categories else []
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=True,
            data=PaginatedResult(items=items, total=len(items), page=1, page_size=50, total_pages=1),
        )
    except Exception:
        pass
    return ApiResponse[PaginatedResult[dict[str, Any]]](
        success=True,
        data=PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1),
    )


@router.get("/funds", summary="List funds", description="List all funds")
async def list_funds(
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    try:
        funds = await brsapi.get_ime_funds()
        items = [
            {"symbol": f.get("symbol", ""), "name": f.get("name", ""), "nav": f.get("price_last") or f.get("price_close") or 0, "date": f.get("date", "")}
            for f in funds
        ] if funds else []
        items.sort(key=lambda x: x["nav"], reverse=True)
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=True,
            data=PaginatedResult(items=items, total=len(items), page=1, page_size=50, total_pages=1),
        )
    except Exception:
        pass
    return ApiResponse[PaginatedResult[dict[str, Any]]](
        success=True,
        data=PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1),
    )
