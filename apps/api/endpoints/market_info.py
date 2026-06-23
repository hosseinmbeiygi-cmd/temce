from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from apps.api.dependencies import get_symbol_service
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse
from services.symbol_service import SymbolService

router = APIRouter()

@router.get("/industries", summary="List industries", description="List all industries sorted by count")
async def list_industries(service: SymbolService = Depends(get_symbol_service)) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    # For now, return empty list as per symbols.py, but this should be implemented in SymbolService
    return ApiResponse[PaginatedResult[dict[str, Any]]](
        success=True, 
        data=PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1)
    )

@router.get("/funds", summary="List funds", description="List all funds")
async def list_funds(service: SymbolService = Depends(get_symbol_service)) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    # For now, return empty list as per symbols.py, but this should be implemented in SymbolService
    return ApiResponse[PaginatedResult[dict[str, Any]]](
        success=True, 
        data=PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1)
    )
