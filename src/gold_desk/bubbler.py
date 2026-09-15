"""Bubbler — حباب + implied USD.

حباب = market - fair.
implied_usd = دلاری که در قیمت بازار نهفته است.

اگر implied_usd > usd_irt بازار → حباب سفته‌بازی.
اگر implied_usd < usd_irt → طلا ارزان‌تر (فرصت).
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    COIN_WEIGHTS,
    GOLD_PURITY_18K,
    GOLD_PURITY_24K,
    GOLD_PURITY_COIN,
    TROY_OUNCE_GRAMS,
)


@dataclass(frozen=True)
class BubbleResult:
    symbol: str
    market: float
    fair: float
    bubble_abs: float
    bubble_pct: float
    implied_usd: float


def _purity_for_symbol(symbol: str) -> float:
    """عیار به صورت کسری (۰.۷۵۰۹، ۰.۹۰۰۹، ۰.۹۹۹۹)."""
    if "GOLD_18K" in symbol or "MELTED" in symbol:
        return GOLD_PURITY_18K / 1000.0
    if "GOLD_24K" in symbol or "GOLD_1G" in symbol:
        return GOLD_PURITY_24K / 1000.0
    if symbol in COIN_WEIGHTS:
        return GOLD_PURITY_COIN / 1000.0
    raise ValueError(symbol)


def _pure_gold_weight(symbol: str) -> float:
    """وزن طلای خالص (گرم) — برای سکه وزن×عیار، برای طلای وزنی 1×عیار."""
    if symbol in COIN_WEIGHTS:
        return COIN_WEIGHTS[symbol] * (_purity_for_symbol(symbol))
    # طلای وزنی: هر گرم با عیار مربوطه
    return 1.0 * _purity_for_symbol(symbol)


def calc_bubble(symbol: str, market: float, fair: float, xau_usd: float) -> BubbleResult:
    """market = قیمت بازار (تومان). fair = ارزش ذاتی (تومان)."""
    bubble_abs = market - fair
    bubble_pct = (bubble_abs / fair * 100.0) if fair > 0 else 0.0

    if xau_usd <= 0:
        implied_usd = 0.0
    else:
        pure_w = _pure_gold_weight(symbol)
        # implied USD = دلار ضمنی نهفته در قیمت بازار
        # market / pure_w = قیمت هر گرم طلای ۲۴ عیار به تومان
        # × 31.1035 / xau_usd = نرخ دلار ضمنی
        implied_usd = (market * TROY_OUNCE_GRAMS) / (pure_w * xau_usd) if pure_w > 0 else 0.0

    return BubbleResult(
        symbol=symbol,
        market=market,
        fair=fair,
        bubble_abs=bubble_abs,
        bubble_pct=bubble_pct,
        implied_usd=implied_usd,
    )
