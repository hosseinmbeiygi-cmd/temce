from __future__ import annotations

import logging
import time

from core.redis_client import get_previous_ema, get_raw_price, set_ema
from services.symbol_registry import get_symbol_meta, is_fair_value_applicable

from core.config import (
    EMA_PERIOD,
    REDIS_KEY_EMA_BUBBLE,
    STALE_DATA_MAX_AGE_SECONDS,
    TROY_OUNCE_GRAMS,
    VALID_RANGES,
)
from core.exceptions import FairValueNotApplicableError, NoDataError, OutlierDataError, StaleDataError

logger = logging.getLogger("brsapi.forecasting_engine")

REFERENCE_XAU = "XAU_USD"
REFERENCE_USD = "USD_IRR_FREE"


def _validate_range(symbol: str, price: float) -> None:
    bounds = VALID_RANGES.get(symbol)
    if bounds and not (bounds["min"] <= price <= bounds["max"]):
        raise OutlierDataError(f"مقدار {symbol}={price} خارج از بازه‌ی مجاز است.")


async def _get_fresh_reference(symbol: str) -> float:
    cached = await get_raw_price(symbol)
    if cached is None:
        raise NoDataError(f"داده‌ای برای {symbol} در کش موجود نیست.")
    age = time.time() - cached["timestamp"]
    if age > STALE_DATA_MAX_AGE_SECONDS:
        raise StaleDataError(f"داده‌ی {symbol} با {int(age)} ثانیه تأخیر، قدیمی (Stale) است.")
    _validate_range(symbol, cached["price"])
    return cached["price"]


async def get_global_rates() -> tuple[float, float]:
    xau = await _get_fresh_reference(REFERENCE_XAU)
    usd = await _get_fresh_reference(REFERENCE_USD)
    return xau, usd


def calculate_fair_value(symbol: str, xau_price: float, usd_price: float) -> float:
    if not is_fair_value_applicable(symbol):
        raise FairValueNotApplicableError(f"ارزش ذاتی مستقیم برای «{symbol}» تعریف نشده.")
    meta = get_symbol_meta(symbol)
    if meta.purity is None:
        raise FairValueNotApplicableError(f"عیار (purity) برای «{symbol}» ثبت نشده است.")
    base_price_per_gram = (xau_price * usd_price) / TROY_OUNCE_GRAMS
    return base_price_per_gram * meta.purity


async def _update_bubble_ema(symbol: str, current_bubble: float) -> tuple[float, str]:
    ema_key = REDIS_KEY_EMA_BUBBLE.format(symbol=symbol)
    previous_ema = await get_previous_ema(ema_key)
    alpha = 2.0 / (EMA_PERIOD + 1)
    if previous_ema is None:
        new_ema = current_bubble
        trend = "neutral"
    else:
        new_ema = (current_bubble * alpha) + (previous_ema * (1 - alpha))
        trend = "increasing" if new_ema > previous_ema else "decreasing" if new_ema < previous_ema else "neutral"
    await set_ema(ema_key, new_ema)
    return new_ema, trend


async def calculate_forecast(symbol: str, current_market_price: float) -> dict:
    xau_price, usd_price = await get_global_rates()
    fair_value = calculate_fair_value(symbol, xau_price, usd_price)
    current_bubble = current_market_price - fair_value
    forecasted_bubble, trend = await _update_bubble_ema(symbol, current_bubble)
    forecasted_price = fair_value + forecasted_bubble
    return {
        "symbol": symbol,
        "fair_value": round(fair_value, 2),
        "current_market_price": current_market_price,
        "current_bubble": round(current_bubble, 2),
        "forecasted_bubble": round(forecasted_bubble, 2),
        "forecasted_price": round(forecasted_price, 2),
        "bubble_trend": trend,
    }


async def calculate_bubble_relative_forecast(symbol: str, current_market_price: float) -> dict:
    ema_key = REDIS_KEY_EMA_BUBBLE.format(symbol=symbol)
    previous_ema = await get_previous_ema(ema_key)
    alpha = 2.0 / (EMA_PERIOD + 1)
    if previous_ema is None:
        new_ema = current_market_price
        trend = "neutral"
    else:
        new_ema = (current_market_price * alpha) + (previous_ema * (1 - alpha))
        trend = "increasing" if new_ema > previous_ema else "decreasing" if new_ema < previous_ema else "neutral"
    await set_ema(ema_key, new_ema)
    return {
        "symbol": symbol,
        "fair_value": None,
        "current_market_price": current_market_price,
        "current_bubble": None,
        "forecasted_bubble": None,
        "forecasted_price": round(new_ema, 2),
        "bubble_trend": trend,
    }


async def forecast_any_symbol(symbol: str, current_market_price: float) -> dict:
    if is_fair_value_applicable(symbol):
        return await calculate_forecast(symbol, current_market_price)
    return await calculate_bubble_relative_forecast(symbol, current_market_price)
