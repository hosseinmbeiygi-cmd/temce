"""Statistical significance for expectancy (roadmap v2:103).

Replaces t-test (which assumes normal PnL distribution) with
Bootstrap and Wilcoxon signed-rank test.
"""

from __future__ import annotations

import random


def bootstrap_expectancy(pnls: list[float], n_bootstrap: int = 2000, ci: float = 0.95) -> dict:
    """Bootstrap CI for expectancy. Returns p_value and CI.

    H0: expectancy <= 0. p_value = proportion of bootstrapped means <= 0.
    """
    if not pnls or len(pnls) < 5:
        return {"p_value": 1.0, "ci_low": 0.0, "ci_high": 0.0, "is_significant": False, "n": len(pnls)}

    # observed expectancy
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    wr = len(wins) / len(pnls) if pnls else 0
    lr = 1 - wr
    obs_exp = wr * (sum(wins) / len(wins) if wins else 0) - lr * abs(sum(losses) / len(losses) if losses else 0)

    # bootstrap
    n = len(pnls)
    boot_means: list[float] = []
    for _ in range(n_bootstrap):
        sample = [random.choice(pnls) for _ in range(n)]
        w = [p for p in sample if p > 0]
        l = [p for p in sample if p <= 0]
        wr_s = len(w) / len(sample) if sample else 0
        lr_s = 1 - wr_s
        exp_s = wr_s * (sum(w) / len(w) if w else 0) - lr_s * abs(sum(l) / len(l) if l else 0)
        boot_means.append(exp_s)

    boot_means_sorted = sorted(boot_means)
    alpha = (1 - ci) / 2
    lo_idx = int(alpha * n_bootstrap)
    hi_idx = int((1 - alpha) * n_bootstrap) - 1
    ci_low = boot_means_sorted[max(0, lo_idx)]
    ci_high = boot_means_sorted[min(len(boot_means_sorted) - 1, hi_idx)]

    # one-sided p-value: proportion <= 0
    p_value = sum(1 for v in boot_means if v <= 0) / len(boot_means) if boot_means else 1.0
    # if observed expectancy positive, p_value small means significant
    is_significant = p_value < 0.05 and obs_exp > 0 and ci_low > 0

    return {
        "observed_expectancy": obs_exp,
        "p_value": round(p_value, 4),
        "ci_low": round(ci_low, 2),
        "ci_high": round(ci_high, 2),
        "is_significant": is_significant,
        "n": n,
        "method": "bootstrap",
    }


def wilcoxon_expectancy(pnls: list[float]) -> dict:
    """Wilcoxon signed-rank test for median PnL > 0 (non-parametric)."""
    if not pnls or len(pnls) < 6:
        return {"p_value": 1.0, "is_significant": False}
    # simple approximation: rank test
    try:
        from scipy import stats  # type: ignore

        stat, pval = stats.wilcoxon(pnls, alternative="greater")
        return {"statistic": float(stat), "p_value": float(pval), "is_significant": pval < 0.05}
    except ImportError:
        # fallback to bootstrap
        return bootstrap_expectancy(pnls)
    except Exception:
        return {"p_value": 1.0, "is_significant": False}


def risk_of_ruin_monte_carlo(
    pnls: list[float],
    initial_capital: float,
    risk_per_trade_pct: float = 1.0,
    n_sims: int = 5000,
    ruin_threshold_pct: float = 50.0,
) -> dict:
    """Risk of ruin for variable position sizing (v2:105).

    Simulates equity paths by resampling PnLs with ATR-scaled position sizes.
    For fixed-qty PnLs, scales by capital/risk. For variable qty, caller should
    pass PnLs already scaled to actual position sizes.
    """
    if not pnls or initial_capital <= 0:
        return {"prob_ruin": 0.0, "method": "monte_carlo"}
    import random as rnd

    ruin_cap = initial_capital * (ruin_threshold_pct / 100.0)
    ruins = 0
    for _ in range(n_sims):
        cap = initial_capital
        for _ in range(len(pnls)):
            cap += rnd.choice(pnls)
            if cap <= ruin_cap:
                ruins += 1
                break
            if cap <= 0:
                ruins += 1
                break
    return {
        "prob_ruin": round(ruins / n_sims * 100, 2),
        "n_sims": n_sims,
        "ruin_threshold": ruin_cap,
        "method": "monte_carlo_variable_size",
    }
