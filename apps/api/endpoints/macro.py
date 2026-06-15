from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_macro_service
from services.macro_service import MacroService

router = APIRouter()


@router.get("/{indicator}")
async def get_indicator(indicator: str, service: MacroService = Depends(get_macro_service)):
    result = await service.get_indicator(indicator)
    return {"success": result.success, "data": result.value}


@router.get("/")
async def list_indicators(service: MacroService = Depends(get_macro_service)):
    result = await service.list_indicators()
    return {"success": result.success, "data": result.value}


@router.get("/{indicator}/history")
async def get_indicator_history(indicator: str, limit: int = 100, service: MacroService = Depends(get_macro_service)):
    result = await service.get_history(indicator, limit)
    return {"success": result.success, "data": result.value}
