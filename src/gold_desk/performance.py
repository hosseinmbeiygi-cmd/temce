"""کارایی و ریسک — معیارهای استاندارد ارزیابی پورتفوی (pure، بدون DB).

پژوهش «کامل‌بودن»: پلتفرم‌های حرفه‌ای علاوه بر بازده (XIRR/MWR) این‌ها را گزارش
می‌کنند: نوسان سالانه، Sharpe، Sortino، بیشترین افت سرمایه (Max Drawdown)، بازده
کل و مقایسه با یک بنچمارک (طلا/دلار/شاخص).

هیچ مقدار جعلی ساخته نمی‌شود: ورودی ناکافی یا نوسان صفر به‌جای صفر/بی‌نهایت،
``None`` برمی‌گرداند.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

DEFAULT_PERIODS_PER_YEAR = 252  # روزهای معاملاتی


def simple_returns(prices: Sequence[float]) -> list[float]:
    """بازده‌های روزانه از یک سری قیمت/ارزش (بدون صفر)."""
    out: list[float] = []
    for prev, cur in zip(prices, prices[1:], strict=False):
        if prev and prev > 0:
            out.append((cur - prev) / prev)
    return out


def total_return_pct(prices: Sequence[float]) -> float | None:
    """بازده کل (=buy&hold) از اولین تا آخرین قیمت."""
    if len(prices) < 2 or not prices[0]:
        return None
    return (prices[-1] / prices[0] - 1.0) * 100.0


def annualized_volatility_pct(
    returns: Sequence[float], periods_per_year: int = DEFAULT_PERIODS_PER_YEAR
) -> float | None:
    """نوسان سالانه‌شده (انحراف معیار نمونه)."""
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(var) * math.sqrt(periods_per_year) * 100.0


def sharpe_ratio(
    returns: Sequence[float],
    risk_free_annual: float = 0.0,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> float | None:
    """نسبت شارپ سالانه‌شده. اگر نوسان صفر باشد ``None`` (نه بی‌نهایت)."""
    if len(returns) < 2:
        return None
    rf_daily = risk_free_annual / periods_per_year
    excess = [r - rf_daily for r in returns]
    sd = annualized_volatility_pct(returns, periods_per_year)
    if not sd:
        return None
    mean = sum(excess) / len(excess)
    return mean * periods_per_year / (sd / 100.0)


def sortino_ratio(
    returns: Sequence[float],
    risk_free_annual: float = 0.0,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> float | None:
    """نسبت سورتینو (انحراف نزولی به‌جای نوسان کل)."""
    if len(returns) < 2:
        return None
    rf_daily = risk_free_annual / periods_per_year
    excess = [r - rf_daily for r in returns]
    downside = [r for r in excess if r < 0]
    if not downside:
        return None
    dd = math.sqrt(sum(r**2 for r in downside) / len(downside)) * math.sqrt(periods_per_year)
    if dd == 0:
        return None
    return (sum(excess) / len(excess)) * periods_per_year / dd


def max_drawdown_pct(equity: Sequence[float]) -> float | None:
    """بیشترین افت از قله (مثبت، درصد)."""
    if len(equity) < 2:
        return None
    peak = equity[0]
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst * 100.0


def gold_silver_ratio(gold_price: float, silver_price: float) -> float | None:
    """نسبت طلا به نقره = چند انس نقره برای یک انس طلا."""
    if not silver_price or silver_price <= 0:
        return None
    return gold_price / silver_price


def relative_to_benchmark_pct(portfolio_return_pct: float | None, benchmark_return_pct: float | None) -> float | None:
    """بازده نسبی به بنچمارک (نقاط درصدی)."""
    if portfolio_return_pct is None or benchmark_return_pct is None:
        return None
    return portfolio_return_pct - benchmark_return_pct


def time_weighted_return_pct(
    valuations: Sequence[float], flows: Sequence[float]
) -> float | None:
    """بازده وزنی‌زمان (TWR) — مستقل از زمان‌بندی جریان‌های نقدی.

    ``valuations[i]`` = ارزش پرتفوی در پایان دورهٔ i و ``flows[i]`` = جریان
    بیرونی همان پایان دوره (واریز مثبت، برداشت منفی). بازده هر زیردوره:
    ``(MV_i − CF_i) / MV_{i−1} − 1`` و سپس زنجیره‌سازی.
    """
    if len(valuations) < 2 or len(valuations) != len(flows):
        return None
    growth = 1.0
    prev = float(valuations[0])
    for i in range(1, len(valuations)):
        if prev <= 0:
            return None
        growth *= (float(valuations[i]) - float(flows[i])) / prev
        prev = float(valuations[i])
    return (growth - 1.0) * 100.0


def value_at_risk_pct(returns: Sequence[float], confidence: float = 0.95) -> float | None:
    """VaR تاریخی (کنوانسیون زیان مثبت). نمونهٔ کم → ``None``."""
    if len(returns) < 20 or not 0 < confidence < 1:
        return None
    ordered = sorted(returns)
    idx = max(0, min(int((1.0 - confidence) * len(ordered)), len(ordered) - 1))
    return max(0.0, -ordered[idx] * 100.0)


def conditional_value_at_risk_pct(returns: Sequence[float], confidence: float = 0.95) -> float | None:
    """CVaR (میانگین زیان دنباله) با کنوانسیون زیان مثبت."""
    if len(returns) < 20 or not 0 < confidence < 1:
        return None
    ordered = sorted(returns)
    cut = max(1, int((1.0 - confidence) * len(ordered)))
    tail = ordered[:cut]
    return max(0.0, -(sum(tail) / len(tail)) * 100.0)


def concentration_pct(weights: Sequence[float]) -> float | None:
    """بیشترین وزن یک دارایی (۰-۱۰۰) برای سنجش تمرکز."""
    if not weights:
        return None
    total = sum(w for w in weights if w > 0)
    if total <= 0:
        return None
    return max(weights) / total * 100.0


__all__ = [
    "DEFAULT_PERIODS_PER_YEAR",
    "annualized_volatility_pct",
    "concentration_pct",
    "conditional_value_at_risk_pct",
    "gold_silver_ratio",
    "max_drawdown_pct",
    "relative_to_benchmark_pct",
    "sharpe_ratio",
    "simple_returns",
    "sortino_ratio",
    "time_weighted_return_pct",
    "total_return_pct",
    "value_at_risk_pct",
]
