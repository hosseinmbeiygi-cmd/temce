from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_smart_money_service
from schemas.common.responses import ApiResponse
from services.smart_money_service import SmartMoneyService

router = APIRouter()


@router.get("/{symbol}", summary="Smart money analysis", description="Analyze smart money flow for a symbol")
async def analyze_smart_money(
    symbol: str,
    service: SmartMoneyService = Depends(get_smart_money_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.analyze(symbol)
    return ApiResponse[dict[str, Any]](
        success=result.success,
        data=result.value,
        error={"message": result.error} if not result.success and result.error else None,
    )
