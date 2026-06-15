from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from apps.api.dependencies import get_symbol_service
from services.symbol_service import SymbolService

router = APIRouter()


@router.post("")
async def create_symbol(body: dict[str, Any] = Body(...), service: SymbolService = Depends(get_symbol_service)):
    rest = {k: v for k, v in body.items() if k not in ("symbol", "name")}
    result = await service.create(symbol=body.get("symbol", ""), name=body.get("name", ""), **rest)
    return {"success": result.success, "data": result.value, "error": result.error if not result.success else None}


@router.get("")
async def list_symbols(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    service: SymbolService = Depends(get_symbol_service),
):
    result = await service.list_all(page, page_size)
    return {"success": result.success, "data": result.value}


@router.get("/search")
async def search_symbols(
    q: str = Query("", min_length=1), page: int = Query(1, ge=1), service: SymbolService = Depends(get_symbol_service)
):
    result = await service.search(q, page)
    return {"success": result.success, "data": result.value}


@router.get("/{symbol}")
async def get_symbol(symbol: str, service: SymbolService = Depends(get_symbol_service)):
    result = await service.get_by_symbol(symbol)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error)
    return {"success": True, "data": result.value}


@router.get("/{symbol}/detail")
async def get_symbol_detail(symbol: str, service: SymbolService = Depends(get_symbol_service)):
    result = await service.get_detail(symbol)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error)
    return {"success": True, "data": result.value}
