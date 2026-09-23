"""توابع کمکی سراسری برای محاسبات آماری."""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import mean


def safe_mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return mean(values)


def safe_std(values: Sequence[float], ddof: int = 1) -> float | None:
    if len(values) < 2:
        return None
    n = len(values)
    m = mean(values)
    var = sum((v - m) ** 2 for v in values) / (n - ddof)
    return math.sqrt(var) if var > 0 else 0.0


def downside_deviation(values: Sequence[float], *, threshold: float = 0.0) -> float | None:
    """انحراف معیار فقط بازدهی‌های منفی نسبت به آستانه."""
    diffs = [v - threshold for v in values if v < threshold]
    if len(diffs) < 2:
        return None
    n = len(diffs)
    m = sum(diffs) / n
    var = sum((d - m) ** 2 for d in diffs) / (n - 1)
    return math.sqrt(var) if var > 0 else 0.0


def sharpe_ratio(returns: Sequence[float], risk_free: float = 0.0) -> float | None:
    excess = [r - risk_free for r in returns]
    sd = safe_std(excess)
    if sd is None or sd == 0:
        return None
    return (mean(excess) / sd) if excess else None


def sortino_ratio(returns: Sequence[float], risk_free: float = 0.0) -> float | None:
    excess = [r - risk_free for r in returns]
    dd = downside_deviation(excess)
    if dd is None or dd == 0:
        return None
    return mean(excess) / dd


def max_drawdown(nav_series: Sequence[float]) -> tuple[float | None, int | None]:
    """محاسبه Max Drawdown و زمان بازیابی (روز).

    Returns: (drawdown, recovery_days) — recovery_days اگر هنوز recover نشده None.
    """
    if not nav_series:
        return None, None
    peak = nav_series[0]
    max_dd = 0.0
    recovery_days = None
    peak_idx = 0
    for i, v in enumerate(nav_series):
        if v > peak:
            peak = v
            peak_idx = i
            if recovery_days is not None and recovery_days > 0:
                # اوج جدید — recovery سنجیده نمی‌شود
                recovery_days = None
        dd = (v - peak) / peak if peak else 0.0
        if dd < max_dd:
            max_dd = dd
            if recovery_days is None:
                # شروع recovery وقتی به peak جدید برسد
                for j in range(peak_idx + 1, len(nav_series)):
                    if nav_series[j] >= peak:
                        recovery_days = j - i
                        break
    return max_dd, recovery_days


def calmar_ratio(cagr: float | None, mdd: float | None) -> float | None:
    if cagr is None or mdd is None or mdd == 0:
        return None
    return cagr / abs(mdd)


def beta_to_market(fund_returns: Sequence[float], market_returns: Sequence[float]) -> float | None:
    if len(fund_returns) != len(market_returns) or len(fund_returns) < 2:
        return None
    fm = mean(fund_returns)
    mm = mean(market_returns)
    cov = sum((f - fm) * (m - mm) for f, m in zip(fund_returns, market_returns, strict=False)) / (len(fund_returns) - 1)
    var = sum((m - mm) ** 2 for m in market_returns) / (len(market_returns) - 1)
    if var == 0:
        return None
    return cov / var


def percentile_rank(value: float, peers: Sequence[float]) -> float | None:
    """صدک مقدار در بین هم‌گروه (۰..۱). None اگر peers خالی باشد."""
    if not peers or len(peers) < 2:
        return None
    sorted_peers = sorted(peers)
    if value <= sorted_peers[0]:
        return 0.0
    if value >= sorted_peers[-1]:
        return 1.0
    below = sum(1 for p in sorted_peers if p < value)
    return below / (len(sorted_peers) - 1)


def hhi(weights: Sequence[float]) -> float | None:
    """شاخص هرفیندال-هیرشمن برای تمرکز پرتفوی."""
    total = sum(weights)
    if total <= 0:
        return None
    norm = [w / total for w in weights]
    return sum(w**2 for w in norm)


def annualized_return(total_return: float, years: float) -> float | None:
    if years <= 0:
        return None
    if total_return <= -1:
        return None
    return (1 + total_return) ** (1 / years) - 1


def correlation(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False)) / n
    var_x = sum((x - mx) ** 2 for x in xs) / n
    var_y = sum((y - my) ** 2 for y in ys) / n
    if var_x == 0 or var_y == 0:
        return None
    return cov / (var_x * var_y) ** 0.5
