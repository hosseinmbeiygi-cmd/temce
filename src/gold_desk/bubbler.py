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
    MESGHAL_GRAMS,
    TROY_OUNCE_GRAMS,
)
from .pricer import purity_ratio


@dataclass(frozen=True)
class BubbleResult:
    symbol: str
    market: float
    fair: float
    bubble_abs: float
    # None = ورودی نامعتبر، نه «حباب صفر». صفر سکویی در scorer امتیاز کامل می‌گرفت
    # و دیتای خراب را سبز می‌کرد؛ None در scorer «کامپوننت گمشده» است (E-M16/C2).
    bubble_pct: float | None
    implied_usd: float | None


def _purity_for_symbol(symbol: str) -> float:
    """عیار به صورت کسر نسبت به ۲۴ عیار (۰.۷۵۰۰۸، ۰.۹۰۰۰۹، ۱.۰).

    از ``pricer.purity_ratio`` استفاده می‌کند تا تعریف عیار در pricer و bubbler
    یکی باشد (E-M17).
    """
    if "GOLD_18K" in symbol or "MELTED" in symbol:
        return purity_ratio(GOLD_PURITY_18K)
    if "GOLD_24K" in symbol or "GOLD_1G" in symbol:
        return purity_ratio(GOLD_PURITY_24K)
    if symbol in COIN_WEIGHTS:
        return purity_ratio(GOLD_PURITY_COIN)
    raise ValueError(symbol)


def _pure_gold_weight(symbol: str) -> float:
    """وزن طلای خالص (گرم) یک واحد نقل‌شده — برای سکه وزن×عیار، برای طلای وزنی
    ۱ گرم×عیار و برای طلای آب‌شده یک مثقال×عیار (بازار مثقالی قیمت می‌زند)."""
    if symbol in COIN_WEIGHTS:
        return COIN_WEIGHTS[symbol] * (_purity_for_symbol(symbol))
    if "MELTED" in symbol:
        return MESGHAL_GRAMS * _purity_for_symbol(symbol)
    # طلای وزنی: هر گرم با عیار مربوطه
    return 1.0 * _purity_for_symbol(symbol)


def calc_bubble(symbol: str, market: float, fair: float, xau_usd: float) -> BubbleResult:
    """market = قیمت بازار (تومان). fair = ارزش ذاتی (تومان)."""
    bubble_abs = market - fair
    # fair<=0 درصد حباب را تعریف‌ناپذیر می‌کند (تقسیم بر صفر)؛ صفر برگرداندن
    # یعنی ادعای «حباب صفر» برای دادهٔ خراب.
    bubble_pct: float | None = (bubble_abs / fair * 100.0) if fair > 0 else None

    # implied USD = دلار ضمنی نهفته در قیمت بازار
    # market / pure_w = قیمت هر گرم طلای ۲۴ عیار به تومان
    # × 31.1035 / xau_usd = نرخ دلار ضمنی
    implied_usd: float | None = None
    if xau_usd > 0:
        pure_w = _pure_gold_weight(symbol)
        if pure_w > 0:
            implied_usd = (market * TROY_OUNCE_GRAMS) / (pure_w * xau_usd)

    return BubbleResult(
        symbol=symbol,
        market=market,
        fair=fair,
        bubble_abs=bubble_abs,
        bubble_pct=bubble_pct,
        implied_usd=implied_usd,
    )
