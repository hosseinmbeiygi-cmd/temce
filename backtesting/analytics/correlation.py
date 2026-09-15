from __future__ import annotations

"""Correlation analysis between assets and with benchmarks."""

import math
from dataclasses import dataclass, field


@dataclass
class CorrelationResult:
    asset_returns: list[float] = field(default_factory=list)
    benchmark_returns: list[float] = field(default_factory=list)
    pearson_r: float = 0.0
    spearman_rho: float = 0.0
    n_periods: int = 0
    beta: float = 0.0
    alpha: float = 0.0
    r_squared: float = 0.0
    rolling_window: int = 20
    rolling_correlations: list[float] = field(default_factory=list)
    regime_correlations: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _pearson_r(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    d1 = sum((x[i] - mx) ** 2 for i in range(n))
    d2 = sum((y[i] - my) ** 2 for i in range(n))
    den = math.sqrt(d1 * d2)
    return num / den if den != 0 else 0.0


def _spearman_rho(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return 0.0

    def rank(v):
        s = sorted([(v[i], i) for i in range(len(v))])
        r = [0.0] * len(v)
        for pos, (_, idx) in enumerate(s):
            r[idx] = pos + 1
        return r

    rx, ry = rank(x), rank(y)
    return _pearson_r(rx, ry)


def compute_correlation(
    asset_prices: list[float],
    benchmark_prices: list[float],
    rolling_window: int = 20,
    risk_free_rate: float = 0.0,
) -> CorrelationResult:
    n = min(len(asset_prices), len(benchmark_prices))
    if n < 3:
        return CorrelationResult(n_periods=n, warnings=["Insufficient data"])
    ar = [(asset_prices[i] / asset_prices[i - 1] - 1) for i in range(1, n)]
    br = [(benchmark_prices[i] / benchmark_prices[i - 1] - 1) for i in range(1, n)]
    pr = _pearson_r(ar, br)
    sr = _spearman_rho(ar, br)
    cov = sum((ar[i] - sum(ar) / len(ar)) * (br[i] - sum(br) / len(br)) for i in range(len(ar))) / len(ar)
    var_b = sum((b - sum(br) / len(br)) ** 2 for b in br) / len(br)
    beta2 = cov / var_b if var_b > 0 else 0.0
    alpha2 = (sum(ar) / len(ar) - risk_free_rate / 252) - beta2 * (sum(br) / len(br) - risk_free_rate / 252)
    ss_res = sum((ar[i] - (alpha2 + beta2 * br[i])) ** 2 for i in range(len(ar)))
    ss_tot = sum((a - sum(ar) / len(ar)) ** 2 for a in ar)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    rolling = []
    for i in range(rolling_window, len(ar)):
        w = ar[i - rolling_window : i]
        x = br[i - rolling_window : i]
        rolling.append(_pearson_r(w, x))
    return CorrelationResult(
        asset_returns=ar,
        benchmark_returns=br,
        pearson_r=pr,
        spearman_rho=sr,
        n_periods=n - 1,
        beta=beta2,
        alpha=alpha2,
        r_squared=r2,
        rolling_window=rolling_window,
        rolling_correlations=rolling,
    )
