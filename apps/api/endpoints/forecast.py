from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from core.logging import get_logger
from schemas.common.responses import ApiResponse
from src.forecasting.service import ALLOWED_HORIZONS, forecast_from_history

router = APIRouter()
logger = get_logger(__name__)


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
    symbol: str = Query(..., description="gold_18k | gold_24k | coin_emami | usd_irr_free | xau_usd | xag_usd"),
    horizon: int = Query(30, ge=1, le=90, description="1,3,7,14,30,90"),
    last_close: float | None = Query(None, description="آخرین قیمت زنده برای anchor (اختیاری)"),
    xau_usd: float | None = Query(None, description="اونس جهانی برای fair_value"),
    usd_irr: float | None = Query(None, description="دلار آزاد برای fair_value"),
) -> ApiResponse[ForecastResponse]:
    """Forecast from real daily closes stored in the DB — no fabricated values."""
    h = min(ALLOWED_HORIZONS, key=lambda x: abs(x - horizon))
    try:
        result = await forecast_from_history(
            symbol=symbol,
            horizon_days=h,
            last_close=last_close,
            xau_usd=xau_usd,
            usd_irr=usd_irr,
        )
    except ValueError as exc:
        return ApiResponse(success=False, error={"message": str(exc)})
    except Exception:
        logger.exception("Forecast failed for %s", symbol)
        return ApiResponse(success=False, error={"message": "پیش‌بینی در دسترس نیست؛ خطای داخلی سرویس."})
    return ApiResponse(success=True, data=result)
