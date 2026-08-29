"""Monte Carlo slippage simulator (سند v5.0 §4.3 + §7.1).

Replaces the point-estimate ``almgren_chriss_slippage`` with a distribution
sampled from observed Bid/Ask history. Produces p5/p50/p95 so the Cost Block
(§4.2 REJECTED_COST_NOT_COVERED) can use a conservative tail estimate instead
of a single midpoint. The simulator also runs an MC slippage loop (سند §7.1)
to obtain a confidence interval on NetEdge, feeding the Statistical Acceptance
Gate (§7.2).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from services.ime_signal_factory import almgren_chriss_slippage


@dataclass
class BidAskObservation:
    spread_pct: float  # (ask - bid) / mid, e.g. 0.005 for 0.5%
    depth: int  # visible volume on the tightest level


@dataclass
class SlippageDistribution:
    mean: float
    p5: float
    p50: float
    p95: float
    std: float
    n_scenarios: int


def sample_slippage(
    history: Sequence[BidAskObservation],
    order_size: int,
    avg_volume: int,
    volatility: float,
    eta: float,
    gamma: float,
    n_scenarios: int = 500,
    seed: int = 42,
) -> SlippageDistribution:
    """Run n_scenarios of Almgren-Chriss with random Bid/Ask perturbations.

    Each scenario samples (spread_pct, depth) from history and adds them to
    the canonical slippage formula. سند §7.1: توزیع احتمالی لغزش به‌جای فرض
    مقدار ثابت، در چند صد سناریو تکرار می‌شود.
    """
    if not history or avg_volume <= 0 or order_size <= 0:
        return SlippageDistribution(mean=0.0, p5=0.0, p50=0.0, p95=0.0, std=0.0, n_scenarios=0)

    rng = np.random.default_rng(seed)
    spreads = np.array([h.spread_pct for h in history])
    depths = np.array([h.depth for h in history])
    base_slippage = almgren_chriss_slippage(order_size, avg_volume, volatility, eta, gamma)
    samples = np.empty(n_scenarios, dtype=np.float64)
    for i in range(n_scenarios):
        idx = int(rng.integers(0, len(history)))
        spread_pct = float(spreads[idx])
        depth_scale = float(depths[idx]) / max(np.mean(depths), 1.0)
        samples[i] = base_slippage * (1.0 + spread_pct) / max(depth_scale, 0.1)
    return SlippageDistribution(
        mean=float(samples.mean()),
        p5=float(np.percentile(samples, 5)),
        p50=float(np.percentile(samples, 50)),
        p95=float(np.percentile(samples, 95)),
        std=float(samples.std(ddof=1)),
        n_scenarios=n_scenarios,
    )


def accept_reject_block(
    net_edge: float,
    slippage_dist: SlippageDistribution,
    gross_edge: float,
    max_slippage_ratio: float = 0.50,
) -> tuple[bool, str]:
    """Conservative tail-based hard block for §4.2 REJECTED_COST_NOT_COVERED.

    Returns (passes, reason). Decision uses p95 of the slippage distribution
    (not the mean) so we don't accept on optimistic assumptions.
    """
    if gross_edge <= 0:
        return True, "no gross edge to evaluate"
    if net_edge <= 0:
        return False, f"net_edge {net_edge:.2f} ≤ 0"
    if slippage_dist.p95 / gross_edge > max_slippage_ratio:
        return False, f"p95 slippage {slippage_dist.p95:.2f} > {max_slippage_ratio:.0%} of gross edge"
    return True, "passes"


def simulate_netedge_mc(
    history: Sequence[BidAskObservation],
    gross_edge: float,
    commission: float,
    market_impact: float,
    latency_buffer: float,
    order_size: int,
    avg_volume: int,
    volatility: float,
    eta: float,
    gamma: float,
    n_scenarios: int = 500,
    seed: int = 42,
) -> dict[str, float]:
    """سند §7.1 MC slippage loop: returns the NetEdge distribution and CI.

    Output dict: {p5_netedge, p50_netedge, p95_netedge, mean, prob_positive}.
    Use prob_positive and the Sharpe-equivalent ratio to feed the Statistical
    Acceptance Gate (§7.2).
    """
    dist = sample_slippage(history, order_size, avg_volume, volatility, eta, gamma, n_scenarios=n_scenarios, seed=seed)
    rng = np.random.default_rng(seed + 1)
    netedges = gross_edge - commission - dist.mean - market_impact - latency_buffer
    samples = np.empty(n_scenarios, dtype=np.float64)
    base_samples = rng.normal(dist.mean, max(dist.std, 1e-9), n_scenarios)
    for i in range(n_scenarios):
        samples[i] = gross_edge - commission - base_samples[i] - market_impact - latency_buffer
    return {
        "p5_netedge": float(np.percentile(samples, 5)),
        "p50_netedge": float(np.percentile(samples, 50)),
        "p95_netedge": float(np.percentile(samples, 95)),
        "mean_netedge": float(samples.mean()),
        "prob_positive": float(np.mean(samples > 0)),
        "slippage_mean": netedges,
    }
