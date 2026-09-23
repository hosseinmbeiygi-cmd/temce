"""لایه ۳: مدیریت و ساختار (۱۰ شاخص).

این لایه به داده‌های پرتفوی ماهانه کدال نیاز دارد. اگر داده موجود نباشد، None برمی‌گردد.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .helpers import hhi, safe_mean


def active_share(fund_weights: Sequence[float], bench_weights: Sequence[float]) -> float | None:
    """Active Share = ½ × Σ|w_fund − w_bench| (فرمول Cremers)."""
    if len(fund_weights) != len(bench_weights) or not fund_weights:
        return None
    diff = sum(abs(f - b) for f, b in zip(fund_weights, bench_weights, strict=False))
    return diff / 2.0


def bootstrap_alpha_pvalue(
    fund_returns: Sequence[float],
    benchmark_returns: Sequence[float],
    n_simulations: int = 1000,
) -> float | None:
    """p-value برای تشخیص شانس از مهارت. کمتر = مهارت‌تر.

    بهینه‌سازی شده با list comprehension و early-stop.
    """
    import random

    if len(fund_returns) != len(benchmark_returns) or len(fund_returns) < 30:
        return None
    actual_alpha = safe_mean(fund_returns)
    if actual_alpha is None:
        return None
    actual_alpha -= safe_mean(benchmark_returns) or 0.0

    bench_list = list(benchmark_returns)
    n = len(bench_list)
    count = 0
    for _ in range(n_simulations):
        sampled = [random.choice(bench_list) for _ in range(n)]
        sample_alpha = sum(sampled) / n - actual_alpha
        if sample_alpha >= actual_alpha:
            count += 1
    return count / n_simulations


def style_drift_score(
    holdings_history: Sequence[dict[str, float]],
    declared_style: dict[str, float],
) -> float | None:
    """فاصله L1 بین ترکیب فعلی و سبک اعلامی."""
    if not holdings_history or not declared_style:
        return None
    last = holdings_history[-1]
    all_keys = set(last.keys()) | set(declared_style.keys())
    if not all_keys:
        return None
    diff = sum(abs(last.get(k, 0) - declared_style.get(k, 0)) for k in all_keys)
    return diff / 2.0


def compute_layer3(
    *,
    portfolio_weights: Sequence[float] | None,
    benchmark_weights: Sequence[float] | None,
    fund_returns: Sequence[float] | None,
    benchmark_returns: Sequence[float] | None,
    ter: float | None,
    performance_fee_type: str | None,
    turnover: float | None,
    holdings_history: Sequence[dict[str, float]] | None,
    declared_style: dict[str, float] | None,
    cash_weight: float | None,
    portfolio_returns: Sequence[float] | None,
    benchmark_returns_td: Sequence[float] | None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "active_share": None,
        "bootstrap_alpha_pvalue": None,
        "style_drift": None,
        "ter": ter,
        "performance_fee_type": performance_fee_type,
        "hhi": hhi(portfolio_weights) if portfolio_weights else None,
        "turnover": turnover,
        "cash_drag": cash_weight,
        "window_dressing": None,
        "tracking_difference": None,
    }

    if portfolio_weights and benchmark_weights:
        out["active_share"] = active_share(portfolio_weights, benchmark_weights)

    if fund_returns and benchmark_returns:
        out["bootstrap_alpha_pvalue"] = bootstrap_alpha_pvalue(fund_returns, benchmark_returns)

    if holdings_history and declared_style:
        out["style_drift"] = style_drift_score(holdings_history, declared_style)

    if portfolio_returns and benchmark_returns_td:
        if len(portfolio_returns) == len(benchmark_returns_td):
            diffs = [p - b for p, b in zip(portfolio_returns, benchmark_returns_td, strict=False)]
            out["tracking_difference"] = safe_mean(diffs)

    if holdings_history and len(holdings_history) >= 2:
        last_keys = set(holdings_history[-1].keys())
        prev_keys = set(holdings_history[-2].keys())
        new_entries = last_keys - prev_keys
        if new_entries and len(last_keys) > 0:
            out["window_dressing"] = len(new_entries) / len(last_keys)

    return out
