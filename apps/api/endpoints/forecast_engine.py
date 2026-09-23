"""forecast_engine endpoints — ادغام BrsApi_Forecasting (ایمن، additive، بدون شکستن /forecast فعلی)."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from schemas.api.legal import LEGAL_DISCLAIMER_FA
from schemas.common.responses import ApiResponse
from src.forecast_engine.exceptions import ForecastingError, NoDataError, StaleDataError
from src.forecast_engine.symbol_registry import SYMBOL_REGISTRY, all_intraday_eligible_symbols

router = APIRouter()


class EngineForecastResponse(BaseModel):
    symbol: str
    fair_value: float | None = None
    current_market_price: float
    current_bubble: float | None = None
    forecasted_bubble: float | None = None
    forecasted_price: float
    bubble_trend: str
    legal_disclaimer: str = Field(default=LEGAL_DISCLAIMER_FA)


class SymbolStatus(BaseModel):
    status: str
    message: str | None = None


# --- Health ---
@router.get("/health", summary="Forecast engine health (Redis + registry)")
async def engine_health():
    from src.forecast_engine.redis_adapter import health_check

    redis_ok = await health_check()
    return ApiResponse(
        success=True,
        data={"status": "ok" if redis_ok else "degraded", "redis": redis_ok, "symbols": len(SYMBOL_REGISTRY)},
    )


# --- Symbols ---
@router.get("/symbols", summary="لیست نمادهای موتور (تک‌منبع حقیقت)")
async def list_engine_symbols():
    return ApiResponse(
        success=True,
        data={
            key: {
                "canonical_id": meta.canonical_id,
                "asset_type": meta.asset_type.value,
                "display_name": meta.display_name,
                "purity": meta.purity,
            }
            for key, meta in SYMBOL_REGISTRY.items()
        },
    )


# --- Single forecast (ایزوله، با نگاشت خطا به HTTP) ---
@router.get("/{symbol}", summary="پیش‌بینی یک نماد با موتور EMA حباب")
async def get_single_engine_forecast(
    symbol: str,
    current_market_price: float = Query(..., gt=0, description="قیمت فعلی بازار"),
):
    from fastapi import HTTPException

    from src.forecast_engine.forecasting_service import forecast_any_symbol

    try:
        result = await forecast_any_symbol(symbol, current_market_price)
        return ApiResponse(success=True, data=result)
    except StaleDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except NoDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForecastingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- Bulk forecast (ایزوله در سطح نماد — صفحه سفید نمی‌شود) ---
@router.get("", summary="پیش‌بینی بالک همه نمادهای واجد شرایط (gold/fx)")
async def get_bulk_engine_forecast(
    symbols: str | None = Query(None, description="لیست comma جدا: gold_18k,usd_irr_free,... (خالی=همه)"),
):
    from src.forecast_engine.forecasting_service import forecast_any_symbol
    from src.forecast_engine.safe_forecast import safe_forecast_many, to_api_response

    # از query param بگیر، اگر خالی بود همه intraday symbols
    requested = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else all_intraday_eligible_symbols()

    # قیمت‌های بازار را از BrsApi (یا stub) بخوان — fallback به قیمت‌های فرضی اگر DB خالی بود
    # برای ادغام ایمن: اگر قیمت در DB نبود، از safe_forecast با LookupError عبور می‌کند و در پاسخ fail می‌شود (نه 500)
    # اینجا قیمت را از cache_raw_price نمی‌خوانیم — بلکه caller باید قیمت را داشته باشد یا از /brsapi بخواند
    # برای UX بهتر: اگر current_market_price نداریم، سعی می‌کنیم از آخرین کش بخوانیم
    from src.forecast_engine.redis_adapter import get_raw_price

    async def _forecast_fn(sym: str) -> dict:
        # اگر نماد خودش XAU/USD یا USD/IRR باشد، قیمت مستقیم بازار را می‌خواهد
        cached = await get_raw_price(sym)  # تلاش برای خواندن قیمت لحظه‌ای اگر از قبل cache شده
        if cached and "price" in cached:
            market_price = float(cached["price"])
        else:
            # fallback: از BrsApi live بخوان؟ فعلا LookupError تا safe_forecast آن را به status تبدیل کند
            raise LookupError(
                f"قیمت بازار برای {sym} در کش موجود نیست — ابتدا /brsapi را sync کنید یا cache_raw_price را صدا بزنید."
            )

        return await forecast_any_symbol(sym, market_price)

    results = await safe_forecast_many(requested, _forecast_fn)
    payload = to_api_response(results)
    return ApiResponse(success=True, data=payload)
