"""لایه ۴: رفتاری و کوانت (۱۲ شاخص)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .helpers import correlation, safe_mean


def behavior_gap(twr: float | None, dwr: float | None) -> float | None:
    if twr is None or dwr is None:
        return None
    return twr - dwr


def persistence_rate(returns_matrix: Sequence[Sequence[float]], top_q: float = 0.25) -> float | None:
    """چند درصد از برندگان دوره N در دوره N+1 هم برنده هستند؟"""
    if len(returns_matrix) < 2:
        return None
    wins, transitions = 0, 0
    for i in range(len(returns_matrix) - 1):
        cur = returns_matrix[i]
        nxt = returns_matrix[i + 1]
        if not cur or not nxt:
            continue
        cur_sorted = sorted(cur, reverse=True)
        n_top = max(1, int(len(cur) * top_q))
        threshold = cur_sorted[n_top - 1]
        winners_idx = [j for j, r in enumerate(cur) if r >= threshold]
        next_sorted = sorted(nxt, reverse=True)
        next_threshold = next_sorted[min(n_top - 1, len(next_sorted) - 1)]
        transitions += len(winners_idx)
        wins += sum(1 for j in winners_idx if nxt[j] >= next_threshold)
    return wins / transitions if transitions else None


def treynor_mazuy_timing(
    fund_excess: Sequence[float],
    market_excess: Sequence[float],
) -> dict[str, float | None]:
    """Market Timing Test (Treynor-Mazuy).

    Regress fund_excess = α + β₁·M + β₂·M² + ε
    β₂ > 0 → timing skill, β₂ < 0 → destructive timing.
    """
    if len(fund_excess) != len(market_excess) or len(fund_excess) < 30:
        return {"alpha": None, "beta": None, "timing_coef": None, "p_timing": None}
    n = len(fund_excess)
    x1 = market_excess
    x2 = [m * m for m in market_excess]
    y = fund_excess

    # OLS ساده با numpy جایگزین نشد — حل دستی معادلات نرمال
    sum_x1 = sum(x1)
    sum_x2 = sum(x2)
    sum_y = sum(y)
    sum_x1x1 = sum(a * b for a, b in zip(x1, x1, strict=False))
    sum_x1x2 = sum(a * b for a, b in zip(x1, x2, strict=False))
    sum_x1y = sum(a * b for a, b in zip(x1, y, strict=False))
    sum_x2x2 = sum(a * b for a, b in zip(x2, x2, strict=False))
    sum_x2y = sum(a * b for a, b in zip(x2, y, strict=False))

    det = sum_x1x1 * sum_x2x2 - sum_x1x2 * sum_x1x2
    if det == 0:
        return {"alpha": None, "beta": None, "timing_coef": None, "p_timing": None}

    beta1 = (sum_x2x2 * sum_x1y - sum_x1x2 * sum_x2y) / det
    beta2 = (sum_x1x1 * sum_x2y - sum_x1x2 * sum_x1y) / det
    alpha = (sum_y - beta1 * sum_x1 - beta2 * sum_x2) / n

    # t-value ساده برای β₂ (approximation بدون آمار کامل)
    residuals = [y[i] - alpha - beta1 * x1[i] - beta2 * x2[i] for i in range(n)]
    rss = sum(r * r for r in residuals)
    sigma2 = rss / max(1, n - 3)
    var_beta2 = sigma2 * sum_x1x1 / det
    se_beta2 = var_beta2**0.5 if var_beta2 > 0 else None
    t_value = (beta2 / se_beta2) if se_beta2 and se_beta2 > 0 else None

    return {
        "alpha": alpha,
        "beta": beta1,
        "timing_coef": beta2,
        "p_timing": t_value,
    }


def compute_layer4(
    *,
    twr: float | None,
    dwr: float | None,
    has_defunct_siblings: bool | None,
    portfolio_weights: Sequence[float] | None,
    daily_volume_per_stock: Sequence[float] | None,
    redemption_rate: float | None,
    market_impact_coef: float | None,
    hidden_repo_pct: float | None,
    benchmark_returns: Sequence[float] | None,
    fund_returns: Sequence[float] | None,
    fund_excess: Sequence[float] | None,
    market_excess: Sequence[float] | None,
    manager_change_at: str | None,
    pre_change_returns: Sequence[float] | None,
    post_change_returns: Sequence[float] | None,
    family_fund_returns: Sequence[Sequence[float]] | None,
    survivorship_adjusted: bool | None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "behavior_gap": behavior_gap(twr, dwr),
        "survivorship_flag": has_defunct_siblings,
        "liquidity_spiral": None,
        "hidden_leverage": hidden_repo_pct,
        "benchmark_gaming": None,
        "performance_persistence": None,
        "market_timing": None,
        "flow_performance": None,
        "redemption_pressure": redemption_rate,
        "diseconomies_of_scale": None,
        "manager_tenure_days": None,
        "post_change_alpha": None,
        "fund_family_correlation": None,
    }

    if portfolio_weights and daily_volume_per_stock and len(portfolio_weights) == len(daily_volume_per_stock):
        impact = 0.0
        for w, vol in zip(portfolio_weights, daily_volume_per_stock, strict=False):
            if vol > 0:
                days_to_liquidate = w / vol
                impact += (market_impact_coef or 0.5) * (days_to_liquidate**0.5) * w
        out["liquidity_spiral"] = impact

    if benchmark_returns and fund_returns and len(benchmark_returns) >= 2:
        out["performance_persistence"] = persistence_rate([benchmark_returns, fund_returns])

    if fund_excess and market_excess:
        timing = treynor_mazuy_timing(fund_excess, market_excess)
        out["market_timing"] = timing["timing_coef"]

    if pre_change_returns and post_change_returns:
        pre = safe_mean(pre_change_returns)
        post = safe_mean(post_change_returns)
        if pre is not None and post is not None:
            out["post_change_alpha"] = post - pre

    if family_fund_returns and len(family_fund_returns) >= 2:
        n = len(family_fund_returns[0])
        if n > 1:
            corrs: list[float] = []
            for i in range(len(family_fund_returns)):
                for j in range(i + 1, len(family_fund_returns)):
                    c = correlation(family_fund_returns[i], family_fund_returns[j])
                    if c is not None:
                        corrs.append(c)
            if corrs:
                out["fund_family_correlation"] = safe_mean(corrs)

    return out
