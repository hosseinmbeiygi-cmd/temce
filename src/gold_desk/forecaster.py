"""Forecaster — پیش‌بینی قیمت طلا/سکه با مدل‌های سبک (بدون ML سنگین).

ترکیب ۳ مدل:
1) Linear Regression روی log(price) — روند لگاریتمی
2) EMA trend — میانگین متحرک نمایی
3) Drift (میانگین بازده روزانه)

خروجی: قیمت پیش‌بینی ۷ و ۳۰ روزه + باند اطمینان بر اساس نوسان تاریخی.
هیچ وابستگی خارجی به sklearn ندارد — pure numpy.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from core.time import utc_now_naive

from .signal_engine import fetch_closes

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ForecastPoint:
    horizon_days: int
    predicted_price: float
    lower_band: float
    upper_band: float
    expected_return_pct: float
    model: str


@dataclass(frozen=True)
class ForecastResult:
    symbol: str
    last_price: float
    last_date: str
    lookback_days: int
    volatility_daily_pct: float
    trend_daily_pct: float
    r_squared: float
    forecasts: list[ForecastPoint]
    summary: str
    recommendation: str
    confidence: float
    model_weights: dict[str, float]


def _linear_regression(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """برگرداندن slope, intercept, R2 برای y ~ x."""
    n = len(x)
    if n < 3:
        return 0.0, float(y[-1]) if n else 0.0, 0.0
    # OLS
    x_mean = x.mean()
    y_mean = y.mean()
    denom = ((x - x_mean) ** 2).sum()
    if denom == 0:
        return 0.0, float(y_mean), 0.0
    slope = ((x - x_mean) * (y - y_mean)).sum() / denom
    intercept = y_mean - slope * x_mean
    y_pred = slope * x + intercept
    ss_res = ((y - y_pred) ** 2).sum()
    ss_tot = ((y - y_mean) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(slope), float(intercept), float(max(0.0, min(1.0, r2)))


def _calc_volatility(closes: list[float]) -> float:
    if len(closes) < 3:
        return 0.0
    arr = np.array(closes, dtype=float)
    rets = np.diff(arr) / arr[:-1]
    return float(np.std(rets, ddof=1))  # daily vol


def _forecast_linear(closes: list[float], horizon: int) -> float:
    """پیش‌بینی با رگرسیون خطی روی log price."""
    if len(closes) < 5:
        return closes[-1] if closes else 0.0
    n = len(closes)
    x = np.arange(n, dtype=float)
    # log price برای روند درصدی
    y = np.log(np.array(closes, dtype=float))
    slope, intercept, _ = _linear_regression(x, y)
    # predict at n-1 + horizon
    log_pred = slope * (n - 1 + horizon) + intercept
    return float(math.exp(log_pred))


def _forecast_ema_trend(closes: list[float], horizon: int, period: int = 14) -> float:
    """پیش‌بینی با EMA drift: آخرین EMA + روند اخیر."""
    if len(closes) < period + 2:
        return closes[-1] if closes else 0.0
    arr = np.array(closes, dtype=float)
    alpha = 2.0 / (period + 1)
    ema = arr[0]
    for p in arr[1:]:
        ema = p * alpha + ema * (1 - alpha)
    # trend = میانگین بازده 7 روز اخیر
    recent = arr[-7:] if len(arr) >= 7 else arr
    if len(recent) < 2:
        return float(ema)
    rets = np.diff(recent) / recent[:-1]
    drift = float(np.mean(rets))
    return float(closes[-1] * ((1 + drift) ** horizon))


def _forecast_drift(closes: list[float], horizon: int) -> float:
    """Naive drift: last_price * (1 + avg_daily_return)^horizon."""
    if len(closes) < 2:
        return closes[-1] if closes else 0.0
    arr = np.array(closes, dtype=float)
    rets = np.diff(arr) / arr[:-1]
    drift = float(np.mean(rets))
    # clip drift to ±2% per day to avoid explosion
    drift = max(-0.02, min(0.02, drift))
    return float(closes[-1] * ((1 + drift) ** horizon))


def _ensemble(closes: list[float], horizon: int, weights: dict[str, float] | None = None) -> tuple[float, str]:
    """ترکیب وزنی ۳ مدل."""
    if weights is None:
        weights = {"linear": 0.5, "ema": 0.3, "drift": 0.2}
    p1 = _forecast_linear(closes, horizon)
    p2 = _forecast_ema_trend(closes, horizon)
    p3 = _forecast_drift(closes, horizon)
    ensemble = p1 * weights["linear"] + p2 * weights["ema"] + p3 * weights["drift"]
    # انتخاب مدل غالب برای توضیح
    best = max(weights, key=lambda k: weights[k])
    return float(ensemble), best


def build_forecast(closes: list[float], symbol: str = "IR_COIN_EMAMI") -> ForecastResult:
    """ساخت پیش‌بینی ۷ و ۳۰ روزه از روی closes."""
    if not closes:
        return ForecastResult(
            symbol=symbol,
            last_price=0,
            last_date=utc_now_naive().strftime("%Y-%m-%d"),
            lookback_days=0,
            volatility_daily_pct=0,
            trend_daily_pct=0,
            r_squared=0,
            forecasts=[],
            summary="داده کافی نیست",
            recommendation="صبر کنید",
            confidence=0.0,
            model_weights={"linear": 0.5, "ema": 0.3, "drift": 0.2},
        )

    last = closes[-1]
    vol = _calc_volatility(closes)  # e.g. 0.015 = 1.5% daily
    # trend daily via LR slope on log
    n = len(closes)
    x = np.arange(n, dtype=float)
    y = np.log(np.array(closes, dtype=float))
    slope, _, r2 = _linear_regression(x, y)
    trend_daily = float((math.exp(slope) - 1) * 100)  # %

    # adaptive weights: اگر R2 بالا → وزن linear بیشتر
    if r2 > 0.7:
        w = {"linear": 0.6, "ema": 0.25, "drift": 0.15}
    elif r2 < 0.3:
        w = {"linear": 0.3, "ema": 0.4, "drift": 0.3}
    else:
        w = {"linear": 0.5, "ema": 0.3, "drift": 0.2}

    points: list[ForecastPoint] = []
    for h in (7, 30):
        pred, model = _ensemble(closes, h, w)
        ret_pct = (pred - last) / last * 100 if last else 0
        # باند اطمینان: ± 1.96 * vol * sqrt(h) * pred (95%)
        band_pct = 1.96 * vol * math.sqrt(h)
        lower = pred * (1 - band_pct)
        upper = pred * (1 + band_pct)
        # اطمینان: R2 * (1 - vol*10) clipped
        points.append(
            ForecastPoint(
                horizon_days=h,
                predicted_price=round(float(pred), 0),
                lower_band=round(float(lower), 0),
                upper_band=round(float(upper), 0),
                expected_return_pct=round(float(ret_pct), 2),
                model=model,
            )
        )

    # confidence کلی
    conf = max(0.2, min(0.9, r2 * 0.8 + 0.2 * (1 - min(1, vol * 20))))
    # guard high volatility
    if vol > 0.03:
        conf *= 0.7

    if trend_daily > 0.3 and r2 > 0.5:
        summary = f"روند صعودی {trend_daily:.2f}٪ روزانه (R²={r2:.2f})"
        rec = "خرید پله‌ای در اصلاح‌های کوچک"
    elif trend_daily < -0.3 and r2 > 0.5:
        summary = f"روند نزولی {trend_daily:.2f}٪ روزانه (R²={r2:.2f})"
        rec = "صبر کنید — فشار فروش ادامه‌دار"
    elif vol > 2.5 / 100:
        summary = f"رژیم پرنوسان (vol {vol*100:.1f}٪ روزانه) — پیش‌بینی کم‌اعتبار"
        rec = "صبر — ریسک بالا"
    else:
        summary = f"روند خنثی {trend_daily:.2f}٪ (R²={r2:.2f}، vol {vol*100:.1f}٪)"
        rec = "نگهداری / DCA خنثی"

    return ForecastResult(
        symbol=symbol,
        last_price=round(float(last), 0),
        last_date=utc_now_naive().strftime("%Y-%m-%d"),
        lookback_days=n,
        volatility_daily_pct=round(float(vol * 100), 2),
        trend_daily_pct=round(float(trend_daily), 3),
        r_squared=round(float(r2), 3),
        forecasts=points,
        summary=summary,
        recommendation=rec,
        confidence=round(float(conf), 2),
        model_weights=w,
    )


async def forecast_symbol(
    session: AsyncSession,
    symbol: str = "IR_COIN_EMAMI",
    days: int = 60,
) -> ForecastResult:
    """پیش‌بینی یک نماد از روی BrsApi هیستوری."""
    closes = await fetch_closes(session, symbol, days)
    return build_forecast(closes, symbol=symbol)


async def forecast_all(
    session: AsyncSession,
    symbols: list[str] | None = None,
    days: int = 60,
) -> list[ForecastResult]:
    """پیش‌بینی چند نماد."""
    if symbols is None:
        symbols = ["IR_COIN_EMAMI", "IR_COIN_BAHAR", "IR_GOLD_18K", "XAUUSD"]
    out: list[ForecastResult] = []
    for sym in symbols:
        try:
            r = await forecast_symbol(session, sym, days)
            out.append(r)
        except Exception as exc:
            logger.warning("forecast failed for %s: %s", sym, exc)
    return out
