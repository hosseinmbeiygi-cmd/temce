"""Real-data forecast service.

Projects future prices from real daily closes stored in the database using a
transparent drift + volatility model. When real history is missing or too
short, a ``ValueError`` is raised — numeric forecasts are never fabricated.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Iterable
from statistics import fmean, pstdev
from typing import Any

from src.features.fair_value import fair_value_gold_irr, premium_log

MIN_HISTORY_POINTS = 20
ALLOWED_HORIZONS = (1, 3, 7, 14, 30, 90)
Z80 = 1.2815515655446004

GOLD_DB_SYMBOLS: dict[str, str] = {
    "gold_18k": "IR_GOLD_18K",
    "gold_24k": "IR_GOLD_24K",
    "gold_1g": "IR_GOLD_1G",
    "coin_emami": "IR_COIN_EMAMI",
    "coin_parsian": "IR_COIN_PARSIAN",
    "coin_half": "IR_COIN_HALF",
    "coin_quarter": "IR_COIN_QUARTER",
    "coin_gerami": "IR_COIN_GERAMI",
}

CURRENCY_DB_SYMBOLS: dict[str, str] = {
    "usd_irr_free": "USD",
    "eur_irr_free": "EUR",
    "gbp_irr_free": "GBP",
    "aed_irr_free": "AED",
    "try_irr_free": "TRY",
}

COMMODITY_NEEDLES: dict[str, str] = {
    "xau_usd": "XAU",
    "xag_usd": "XAG",
}


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _round_price(x: float) -> float | int:
    return round(x, 4) if abs(x) < 10_000 else int(round(x))


def _quality_bands(sigma_daily: float) -> tuple[str, str]:
    annual_vol_pct = sigma_daily * math.sqrt(252) * 100
    if annual_vol_pct < 20:
        return "low", "low"
    if annual_vol_pct < 45:
        return "normal", "medium"
    return "high", "high"


def project_from_closes(
    symbol: str,
    closes: Iterable[float],
    horizon_days: int,
    last_close: float | None = None,
    xau_usd: float | None = None,
    usd_irr: float | None = None,
    data_as_of: str | None = None,
) -> dict[str, Any]:
    """Project prices from real closes (drift + volatility random-walk model)."""
    if horizon_days not in ALLOWED_HORIZONS:
        raise ValueError("horizon must be one of 1,3,7,14,30,90")

    clean = [float(c) for c in closes if c is not None and float(c) > 0]
    if len(clean) < MIN_HISTORY_POINTS:
        raise ValueError(
            f"تاریخچه واقعی کافی برای «{symbol}» موجود نیست: "
            f"{len(clean)} روز (حداقل {MIN_HISTORY_POINTS} روز لازم است)."
        )

    # A live anchor is always the base when provided (callers pass real market
    # prices). When it deviates strongly from stored history, the stored series
    # is treated as stale/unit-mismatched: volatility is kept but drift is zeroed.
    anchor = float(last_close) if last_close and float(last_close) > 0 else None
    if anchor is not None and anchor > 0:
        clean.append(anchor)
    base = clean[-1]
    stale_anchor = anchor is not None and (anchor / clean[-2] > 3.0 or anchor / clean[-2] < 1 / 3.0)

    returns = [math.log(clean[i] / clean[i - 1]) for i in range(1, len(clean))]
    mu = fmean(returns)
    if stale_anchor:
        mu = 0.0
    mu = max(-0.005, min(0.005, mu))
    sigma = max(0.002, min(0.06, pstdev(returns) or 1e-6))

    today = dt.date.today()
    forecast: list[dict[str, Any]] = []
    for t in range(1, horizon_days + 1):
        p50 = base * math.exp(mu * t)
        spread = Z80 * sigma * math.sqrt(t)
        prob_up = min(0.95, max(0.05, _norm_cdf((mu / sigma) * math.sqrt(t))))
        forecast.append(
            {
                "date": (today + dt.timedelta(days=t)).isoformat(),
                "p50": _round_price(p50),
                "p_lower": _round_price(p50 * math.exp(-spread)),
                "p_upper": _round_price(p50 * math.exp(spread)),
                "direction_probability_up": round(prob_up, 3),
            }
        )

    volatility, risk_level = _quality_bands(sigma)
    history_points = len(clean) - (1 if anchor is not None else 0)

    meta: dict[str, Any] = {
        "history_points": history_points,
        "method": "drift + volatility random-walk (real closes)",
        "mu_daily": round(mu, 6),
        "sigma_daily": round(sigma, 6),
        "annualized_drift_pct": round((math.exp(mu * 252) - 1) * 100, 2),
        "annualized_vol_pct": round(sigma * math.sqrt(252) * 100, 2),
        "last_close": _round_price(base),
        "history_last_close": _round_price(clean[-2] if anchor is not None else clean[-1]),
        "anchor_used": anchor is not None,
        "stale_anchor": stale_anchor,
        "disclaimer": "پیش‌بینی آماری محاسبه‌شده از تاریخچه واقعی بازار — نه مدل آموزش‌دیده و نه تضمین بازده.",
    }
    if stale_anchor:
        meta["note"] = "قیمت زنده با تاریخچه ذخیره‌شده فاصله زیادی دارد؛ دریفت صفر شده و فقط نوسان واقعی اعمال شده است."

    if xau_usd and usd_irr:
        try:
            fv = float(fair_value_gold_irr(xau_usd, usd_irr))
            meta["fair_value_irr"] = int(fv)
            meta["premium_log"] = round(premium_log(base, fv), 4)
        except Exception:
            meta["fair_value_irr"] = None
            meta["premium_log"] = None

    return {
        "symbol": symbol,
        "horizon_days": horizon_days,
        "data_as_of": data_as_of or dt.datetime.now(dt.UTC).isoformat(),
        "model": {
            "name": "statistical_baseline",
            "version": "drift+vol_v1",
            "trained_at": None,
            "note": "پیش‌بینی آماری (دریفت + نوسان) از تاریخچه واقعی دیتابیس — نه مدل آموزش‌دیده.",
        },
        "forecast": forecast,
        "quality": {
            "status": "stale_anchor" if stale_anchor else "good",
            "is_stale": bool(stale_anchor),
            "last_data_age_minutes": 0,
            "history_points": history_points,
        },
        "risk": {
            "level": risk_level,
            "volatility": volatility,
            "drift_detected": abs(mu) > 2 * sigma / math.sqrt(len(returns)),
        },
        "meta": meta,
    }


def forecast_gold(
    symbol: str,
    horizon_days: int,
    last_close: float | None = None,
    xau_usd: float | None = None,
    usd_irr: float | None = None,
    closes: Iterable[float] | None = None,
    data_as_of: str | None = None,
) -> dict[str, Any]:
    """Backward-compatible wrapper — real closes are mandatory."""
    if not closes:
        raise ValueError(
            "پیش‌بینی بدون تاریخچه واقعی غیرمجاز است؛ پارامتر closes الزامی است "
            "(forecast_from_history را استفاده کنید)."
        )
    return project_from_closes(
        symbol=symbol,
        closes=closes,
        horizon_days=horizon_days,
        last_close=last_close,
        xau_usd=xau_usd,
        usd_irr=usd_irr,
        data_as_of=data_as_of,
    )


async def _load_history_rows(session: Any, symbol: str) -> list[tuple[str, float]]:
    from sqlalchemy import select

    if symbol in GOLD_DB_SYMBOLS:
        from brsapi.models.commodity import GoldCoinHistoryModel as Model

        stmt = (
            select(Model.date, Model.price_close)
            .where(Model.symbol == GOLD_DB_SYMBOLS[symbol], Model.price_close.isnot(None))
            .order_by(Model.date.asc())
            .limit(4000)
        )
        rows = (await session.execute(stmt)).all()
        return [(str(d), float(p)) for d, p in rows if d and p and float(p) > 0]

    if symbol in CURRENCY_DB_SYMBOLS:
        from brsapi.models.commodity import GoldCurrencyProDailyHistoryModel as Model

        stmt = (
            select(Model.date, Model.price_close)
            .where(Model.symbol == CURRENCY_DB_SYMBOLS[symbol], Model.price_close.isnot(None))
            .order_by(Model.date.asc())
            .limit(4000)
        )
        rows = (await session.execute(stmt)).all()
        return [(str(d), float(p)) for d, p in rows if d and p and float(p) > 0]

    needle = COMMODITY_NEEDLES.get(symbol) or symbol.upper()
    from brsapi.models.commodity import CommodityPriceModel as Model

    stmt = (
        select(Model.date, Model.price, Model.time_unix)
        .where(Model.symbol.ilike(f"%{needle}%"), Model.price.isnot(None))
        .order_by(Model.date.asc(), Model.time_unix.asc())
        .limit(4000)
    )
    rows = (await session.execute(stmt)).all()
    by_date: dict[str, float] = {}
    for date, price, _ts in rows:
        if date and price and float(price) > 0:
            by_date[str(date)] = float(price)
    return [(d, by_date[d]) for d in sorted(by_date)]


async def forecast_from_history(
    symbol: str,
    horizon_days: int,
    last_close: float | None = None,
    xau_usd: float | None = None,
    usd_irr: float | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    """Load real daily closes for ``symbol`` and project the requested horizon."""
    known = symbol in GOLD_DB_SYMBOLS or symbol in CURRENCY_DB_SYMBOLS or symbol in COMMODITY_NEEDLES
    if not known:
        raise ValueError(
            f"نماد «{symbol}» برای پیش‌بینی پشتیبانی نمی‌شود. "
            f"نمادهای مجاز: {', '.join(sorted({*GOLD_DB_SYMBOLS, *CURRENCY_DB_SYMBOLS, *COMMODITY_NEEDLES}))}"
        )

    if session is not None:
        rows = await _load_history_rows(session, symbol)
        return project_from_closes(
            symbol=symbol,
            closes=[p for _, p in rows],
            horizon_days=horizon_days,
            last_close=last_close,
            xau_usd=xau_usd,
            usd_irr=usd_irr,
            data_as_of=rows[-1][0] if rows else None,
        )

    from core.database import async_session_factory

    if async_session_factory is None:
        raise ValueError("اتصال دیتابیس برقرار نیست؛ پیش‌بینی واقعی امکان‌پذیر نیست.")

    async with async_session_factory() as new_session:
        rows = await _load_history_rows(new_session, symbol)
    return project_from_closes(
        symbol=symbol,
        closes=[p for _, p in rows],
        horizon_days=horizon_days,
        last_close=last_close,
        xau_usd=xau_usd,
        usd_irr=usd_irr,
        data_as_of=rows[-1][0] if rows else None,
    )
