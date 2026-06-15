from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from apps.api.dependencies import get_smart_money_service
from services.smart_money_service import SmartMoneyService

router = APIRouter()


@router.get("/{symbol}")
async def analyze_smart_money(symbol: str, service: SmartMoneyService = Depends(get_smart_money_service)):
    result = await service.analyze(symbol)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error)
    data = result.value
    from schemas.api.smart_money import SmartMoneyAnalysisResponse

    resp = SmartMoneyAnalysisResponse(
        symbol=symbol,
        smart_money_score=data["smart_money_score"],
        phase=data["phase"],
        scores=data["scores"],
        penalties=data["penalties"],
        features=data["features"],
        breakout_features=data["breakout_features"],
    )
    return {"success": True, "data": resp.model_dump()}
