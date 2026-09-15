"""Attribution Analysis — decomposes returns into sources.

Sources of return:
- Alpha (skill-based excess return)
- Beta (market exposure)
- Sector allocation effect
- Stock selection effect
- Transaction cost drag
- Timing effect
- Liquidity premium

Also provides:
- Benchmark-relative metrics
- Factor exposure analysis
- Brinson attribution for portfolios
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AttributionResult:
    """Decomposition of portfolio return."""

    total_return: float = 0.0
    benchmark_return: float = 0.0

    # Brinson attribution
    allocation_effect: float = 0.0  # sector allocation
    selection_effect: float = 0.0  # stock selection
    interaction_effect: float = 0.0  # interaction
    total_active_return: float = 0.0  # portfolio - benchmark

    # Factor attribution
    alpha: float = 0.0
    beta: float = 0.0
    r_squared: float = 0.0

    # Cost attribution
    transaction_cost_drag: float = 0.0
    slippage_drag: float = 0.0
    management_fee_drag: float = 0.0

    # Risk attribution
    tracking_error: float = 0.0
    information_ratio: float = 0.0
    upside_capture: float = 0.0
    downside_capture: float = 0.0

    details: dict[str, Any] = field(default_factory=dict)


class AttributionEngine:
    """Decomposes portfolio returns into attribution factors."""

    def compute(
        self,
        portfolio_returns: list[float],
        benchmark_returns: list[float],
        risk_free_rate: float = 0.0,
    ) -> AttributionResult:
        """Compute attribution between portfolio and benchmark."""
        result = AttributionResult()

        if len(portfolio_returns) < 2 or len(benchmark_returns) < 2:
            return result

        n = min(len(portfolio_returns), len(benchmark_returns))
        port = np.array(portfolio_returns[-n:])
        bench = np.array(benchmark_returns[-n:])

        # Total returns
        result.total_return = float(np.prod(1 + port) - 1)
        result.benchmark_return = float(np.prod(1 + bench) - 1)
        result.total_active_return = result.total_return - result.benchmark_return

        # Alpha / Beta regression
        result.alpha, result.beta, result.r_squared = self._regression(port, bench, risk_free_rate)

        # Tracking error
        active = port - bench
        result.tracking_error = float(np.std(active, ddof=1) * np.sqrt(252)) if len(active) > 1 else 0.0

        # Information ratio
        if result.tracking_error > 0:
            result.information_ratio = result.alpha / result.tracking_error

        # Capture ratios
        result.upside_capture = self._capture_ratio(port, bench, direction="up")
        result.downside_capture = self._capture_ratio(port, bench, direction="down")

        # Cost attribution (approximation)
        result.transaction_cost_drag = 0.0  # needs trade data

        return result

    def compute_brinson(
        self,
        portfolio_weights: dict[str, float],
        benchmark_weights: dict[str, float],
        portfolio_returns: dict[str, float],
        benchmark_returns: dict[str, float],
    ) -> AttributionResult:
        """Brinson attribution for multi-asset portfolios."""
        result = AttributionResult()

        all_sectors = set(list(portfolio_weights.keys()) + list(benchmark_weights.keys()))

        for sector in all_sectors:
            wp = portfolio_weights.get(sector, 0.0)
            wb = benchmark_weights.get(sector, 0.0)
            rp = portfolio_returns.get(sector, 0.0)
            rb = benchmark_returns.get(sector, 0.0)

            result.allocation_effect += (wp - wb) * rb
            result.selection_effect += wb * (rp - rb)
            result.interaction_effect += (wp - wb) * (rp - rb)

        result.total_active_return = result.allocation_effect + result.selection_effect + result.interaction_effect
        return result

    @staticmethod
    def _regression(y: np.ndarray, x: np.ndarray, rf: float = 0.0) -> tuple[float, float, float]:
        """Simple OLS regression: y = alpha + beta * x + epsilon."""
        if len(x) < 2 or len(y) < 2:
            return 0.0, 0.0, 0.0

        excess_y = y - rf / 252
        excess_x = x - rf / 252

        mean_x = np.mean(excess_x)
        mean_y = np.mean(excess_y)

        cov_xy = np.sum((excess_x - mean_x) * (excess_y - mean_y)) / (len(x) - 1)
        var_x = np.sum((excess_x - mean_x) ** 2) / (len(x) - 1)

        if var_x < 1e-12:
            return 0.0, 0.0, 0.0

        beta = cov_xy / var_x
        alpha_daily = mean_y - beta * mean_x
        alpha_annual = alpha_daily * 252

        # R-squared
        ss_res = np.sum((excess_y - (alpha_daily + beta * excess_x)) ** 2)
        ss_tot = np.sum((excess_y - mean_y) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        return float(alpha_annual), float(beta), float(r_squared)

    @staticmethod
    def _capture_ratio(portfolio: np.ndarray, benchmark: np.ndarray, direction: str = "up") -> float:
        """Compute upside or downside capture ratio."""
        mask = benchmark > 0 if direction == "up" else benchmark < 0

        if not np.any(mask):
            return 1.0

        port_in = portfolio[mask]
        bench_in = benchmark[mask]

        port_prod = np.prod(1 + port_in)
        bench_prod = np.prod(1 + bench_in)

        if bench_prod <= 0:
            return 1.0

        return float(port_prod / bench_prod)
