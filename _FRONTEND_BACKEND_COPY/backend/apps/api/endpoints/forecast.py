from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from schemas.common.responses import ApiResponse
from src.forecasting.service import forecast_gold

router = APIRouter()


class ForecastResponse(BaseModel):
    symbol: str
    horizon_days: int
    data_as_of: str
    model: dict
    forecast: list[dict]
    quality: dict
    risk: dict
    meta: dict | None = None


@router.get("", response_model=ApiResponse[ForecastResponse])
async def get_forecast(
    symbol: str = Query(..., description="gold_18k | usd_irr_free | xau_usd | xag_usd", examples=["xag_usd"]),
    horizon: int = Query(30, ge=1, le=90, description="1,3,7,14,30,90"),
    last_close: float = Query(81200000, description="آخرین قیمت بسته برای anchor"),
    xau_usd: float | None = Query(None, description="اونس جهانی برای fair_value"),
    usd_irr: float | None = Query(None, description="دلار آزاد برای fair_value"),
) -> ApiResponse[ForecastResponse]:
    # نگاشت horizon به نزدیک‌ترین مقدار مجاز (direct multi-horizon)
    allowed = [1, 3, 7, 14, 30, 90]
    h = min(allowed, key=lambda x: abs(x - horizon))
    result = forecast_gold(symbol=symbol, horizon_days=h, last_close=last_close, xau_usd=xau_usd, usd_irr=usd_irr)
    return ApiResponse(success=True, data=result)
