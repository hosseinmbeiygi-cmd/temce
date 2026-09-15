from __future__ import annotations

"""Statistical significance tests for strategy evaluation.

Replacements for parametric tests that assume normality:
- Bootstrap confidence intervals for expectancy
- Sign test for median PnL
- Wilcoxon signed-rank test
"""

import math
import random
from dataclasses import dataclass, field

random.seed(42)


@dataclass
class BootstrapResult:
    n_bootstrap: int
    observed_expectancy: float
    ci_lower_95: float
    ci_upper_95: float
    ci_lower_99: float
    ci_upper_99: float
    p_below_zero: float
    is_significant: bool
    distribution: list[float] = field(default_factory=list)


@dataclass
class SignTestResult:
    n_positive: int
    n_total: int
    positive_ratio: float
    p_value: float
    is_significant: bool


@dataclass
class WilcoxonResult:
    statistic: float
    p_value: float
    effect_size: float
    is_significant: bool


def bootstrap_expectancy(trade_pnls: list[float], n_iterations: int = 10000) -> BootstrapResult:
    n = len(trade_pnls)
    if n < 5:
        return BootstrapResult(
            n_bootstrap=n_iterations,
            observed_expectancy=0,
            ci_lower_95=0,
            ci_upper_95=0,
            ci_lower_99=0,
            ci_upper_99=0,
            p_below_zero=1.0,
            is_significant=False,
            distribution=[],
        )
    obs = sum(trade_pnls) / n
    means = []
    for _ in range(n_iterations):
        sample = [random.choice(trade_pnls) for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    ci95_l = means[int(n_iterations * 0.025)]
    ci95_u = means[int(n_iterations * 0.975)]
    ci99_l = means[int(n_iterations * 0.005)]
    ci99_u = means[int(n_iterations * 0.995)]
    p_zero = sum(1 for m in means if m <= 0) / n_iterations
    return BootstrapResult(
        n_bootstrap=n_iterations,
        observed_expectancy=round(obs, 6),
        ci_lower_95=round(ci95_l, 6),
        ci_upper_95=round(ci95_u, 6),
        ci_lower_99=round(ci99_l, 6),
        ci_upper_99=round(ci99_u, 6),
        p_below_zero=round(p_zero, 4),
        is_significant=p_zero < 0.05,
        distribution=means,
    )


def sign_test(pnls: list[float]) -> SignTestResult:
    n_pos = sum(1 for p in pnls if p > 0)
    n = len(pnls)
    if n < 5:
        return SignTestResult(n_pos, n, n_pos / n if n else 0, 1.0, False)
    from math import comb

    p = sum(comb(n, k) * (0.5**n) for k in range(n_pos, n + 1))
    return SignTestResult(n_pos, n, round(n_pos / n, 4), round(p, 4), p < 0.05)


def wilcoxon_signed_rank(pnls: list[float]) -> WilcoxonResult:
    n = len(pnls)
    if n < 5:
        return WilcoxonResult(0, 1.0, 0, False)
    abs_pnls = [(abs(p), p) for p in pnls if p != 0]
    abs_pnls.sort(key=lambda x: x[0])
    ranks = {i + 1: (abs_val, sign > 0) for i, (abs_val, sign) in enumerate(abs_pnls)}
    w_plus = sum(r for r, (_, pos) in ranks.items() if pos)
    w_minus = sum(r for r, (_, pos) in ranks.items() if not pos)
    w_stat = min(w_plus, w_minus)
    n_valid = len(abs_pnls)
    mu = n_valid * (n_valid + 1) / 4
    sigma = math.sqrt(n_valid * (n_valid + 1) * (2 * n_valid + 1) / 24)
    z = (w_stat - mu) / sigma if sigma > 0 else 0
    p_val = 2 * (1 - _norm_cdf(abs(z)))
    z = abs(z)
    eff = z / math.sqrt(n_valid) if n_valid > 0 else 0
    return WilcoxonResult(round(w_stat, 2), round(p_val, 4), round(eff, 4), p_val < 0.05)


def _norm_cdf(x: float) -> float:
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0
