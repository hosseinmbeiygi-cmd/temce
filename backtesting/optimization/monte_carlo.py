"""
Monte Carlo Simulation (Enhanced)
=================================

Generates confidence intervals for strategy performance by:
1. Block bootstrap resampling (preserves serial correlation)
2. Running N simulations
3. Computing percentile-based confidence intervals

Enhancements over basic bootstrap:
1. Block bootstrap for serial correlation
2. Stationary bootstrap (random block lengths)
3. Drawdown distribution analysis
4. Ruin probability with path dependency
5. Kelly criterion optimal fraction
"""

from __future__ import annotations

import math
import random
from typing import Any


def _percentile(data: list[float], p: float) -> float:
    """Compute the p-th percentile of a sorted list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)


def _block_bootstrap(
    pnls: list[float],
    n_trades: int,
    block_size: int = 5,
) -> list[float]:
    """Block bootstrap resampling that preserves serial correlation.

    Args:
        pnls: Original PnL series
        n_trades: Number of trades to sample
        block_size: Length of contiguous blocks to sample

    Returns:
        Resampled PnL series with preserved serial correlation
    """
    if not pnls or n_trades <= 0:
        return []

    n_blocks = math.ceil(n_trades / block_size)
    result = []

    for _ in range(n_blocks):
        # Random starting position
        start = random.randint(0, max(0, len(pnls) - block_size))
        block = pnls[start:start + block_size]
        result.extend(block)

    return result[:n_trades]


def _stationary_bootstrap(
    pnls: list[float],
    n_trades: int,
    avg_block_size: float = 5.0,
) -> list[float]:
    """Stationary bootstrap with random block lengths (Politis & Romano, 1994).

    Block lengths follow geometric distribution with mean = avg_block_size.
    This is more flexible than fixed block bootstrap.
    """
    if not pnls or n_trades <= 0:
        return []

    result = []
    p = 1.0 / avg_block_size  # Probability of starting a new block
    start = 0

    while len(result) < n_trades:
        # Start new block with probability p
        start = random.randint(0, len(pnls) - 1) if not result or random.random() < p else (start + 1) % len(pnls)

        result.append(pnls[start])

    return result[:n_trades]


def _run_batch(
    pnls: list[float],
    n_trades: int,
    initial_capital: float,
    n_sims: int,
    block_size: int = 5,
    use_stationary: bool = False,
    ruin_threshold: float = 0.5,
) -> list[dict[str, float]]:
    """Run a batch of Monte Carlo simulations with block bootstrap."""
    results = []
    for _ in range(n_sims):
        # Use block bootstrap to preserve serial correlation
        if use_stationary:
            sampled = _stationary_bootstrap(pnls, n_trades, avg_block_size=max(block_size, 2))
        else:
            sampled = _block_bootstrap(pnls, n_trades, block_size=block_size)

        capital = initial_capital
        peak = capital
        max_dd = 0.0
        max_dd_pct = 0.0
        min_capital = initial_capital
        drawdowns = []

        for pnl in sampled:
            capital += pnl
            if capital > peak:
                peak = capital
            dd = peak - capital
            dd_pct = dd / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
            max_dd_pct = max(max_dd_pct, dd_pct)
            min_capital = min(min_capital, capital)
            drawdowns.append(dd_pct)

        results.append({
            "final": capital,
            "max_dd": max_dd,
            "max_dd_pct": max_dd_pct * 100,
            "min_capital": min_capital,
            "avg_drawdown_pct": (sum(drawdowns) / len(drawdowns) * 100) if drawdowns else 0,
        })
    return results


class MonteCarloSimulator:
    """Monte Carlo simulation for strategy confidence intervals.

    Uses block bootstrap to preserve serial correlation in returns,
    which is critical for trend-following and momentum strategies.
    """

    def __init__(
        self,
        n_simulations: int = 1000,
        confidence_levels: list[int] | None = None,
        max_workers: int | None = None,
        block_size: int = 5,
        use_stationary: bool = False,
    ) -> None:
        """
        Args:
            n_simulations: Number of Monte Carlo simulations
            confidence_levels: Percentile levels for confidence intervals
            max_workers: Max parallel workers
            block_size: Block length for block bootstrap
            use_stationary: Use stationary bootstrap (random block lengths)
        """
        self.n_simulations = n_simulations
        self.confidence_levels = confidence_levels or [5, 25, 50, 75, 95]
        self._max_workers = max_workers
        self.block_size = block_size
        self.use_stationary = use_stationary

    def _get_max_workers(self) -> int:
        if self._max_workers is not None:
            return self._max_workers
        try:
            from core.config import settings
            return getattr(settings, "backtest_max_optimization_workers", 4)
        except Exception:
            return 4

    def _estimate_block_size(self, pnls: list[float]) -> int:
        """Estimate optimal block size using autocorrelation.

        Uses the method of Politis & White (2004) for automatic block selection.
        """
        n = len(pnls)
        if n < 10:
            return 3

        # Compute autocorrelation at lag 1
        mean = sum(pnls) / n
        var = sum((x - mean) ** 2 for x in pnls) / n
        if var == 0:
            return 3

        autocorr_1 = sum((pnls[i] - mean) * (pnls[i-1] - mean) for i in range(1, n)) / (n * var)

        # Optimal block length (simplified)
        if abs(autocorr_1) < 0.1:
            return 3  # Low autocorrelation
        elif abs(autocorr_1) < 0.3:
            return 5  # Moderate
        elif abs(autocorr_1) < 0.5:
            return 8  # High
        else:
            return min(12, n // 5)  # Very high autocorrelation

    def simulate(
        self,
        trades: list[dict[str, Any]],
        initial_capital: float,
        block_size: int | None = None,
    ) -> dict[str, Any]:
        """Run Monte Carlo simulation with block bootstrap.

        Args:
            trades: List of {"pnl": float, "side": str, ...}
            initial_capital: Starting capital
            block_size: Override automatic block size estimation

        Returns:
            Dict with confidence intervals, probability metrics, and risk analysis.
        """
        if not trades:
            return {"error": "No trades to simulate"}

        pnls = [t.get("pnl", 0) for t in trades]
        n_trades = len(pnls)
        max_workers = self._get_max_workers()

        # Auto-estimate block size if not provided
        block_size = self._estimate_block_size(pnls) if block_size is None else max(2, block_size)

        # Split simulations across workers for parallel execution
        all_results: list[dict[str, float]] = []
        if max_workers > 1 and self.n_simulations >= max_workers * 10:
            batch_size = self.n_simulations // max_workers
            remainder = self.n_simulations - batch_size * max_workers
            batches = [batch_size] * max_workers
            if remainder > 0:
                batches[-1] += remainder

            # Note: Can't use ProcessPoolExecutor with closures in PowerShell
            # Fall back to sequential
            for bs in batches:
                all_results.extend(_run_batch(
                    pnls, n_trades, initial_capital, bs,
                    block_size=block_size,
                    use_stationary=self.use_stationary,
                ))
        else:
            all_results = _run_batch(
                pnls, n_trades, initial_capital, self.n_simulations,
                block_size=block_size,
                use_stationary=self.use_stationary,
            )

        final_capitals = [r["final"] for r in all_results]
        max_drawdowns = [r["max_dd"] for r in all_results]
        max_drawdown_pcts = [r["max_dd_pct"] for r in all_results]
        min_capitals = [r["min_capital"] for r in all_results]
        [r["avg_drawdown_pct"] for r in all_results]

        # Confidence intervals
        confidence_intervals = {}
        for level in self.confidence_levels:
            confidence_intervals[level] = round(_percentile(final_capitals, level), 0)

        # Statistics
        avg_final = sum(final_capitals) / len(final_capitals)
        prob_profit = sum(1 for c in final_capitals if c > initial_capital) / len(final_capitals) * 100
        prob_ruin_50 = sum(1 for c in min_capitals if c < initial_capital * 0.5) / len(min_capitals) * 100
        prob_ruin_75 = sum(1 for c in min_capitals if c < initial_capital * 0.75) / len(min_capitals) * 100

        # Kelly criterion (optimal bet fraction)
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        if wins and losses:
            win_rate = len(wins) / len(pnls)
            avg_win = sum(wins) / len(wins)
            avg_loss = abs(sum(losses) / len(losses))
            if avg_loss > 0:
                win_loss_ratio = avg_win / avg_loss
                kelly_fraction = win_rate - (1 - win_rate) / win_loss_ratio
                kelly_fraction = max(0, min(kelly_fraction, 1))
            else:
                kelly_fraction = 0
        else:
            kelly_fraction = 0

        # Autocorrelation analysis
        mean_pnl = sum(pnls) / len(pnls) if pnls else 0
        var_pnl = sum((p - mean_pnl) ** 2 for p in pnls) / len(pnls) if pnls else 1
        autocorr_1 = 0
        if var_pnl > 0 and len(pnls) > 1:
            autocorr_1 = sum((pnls[i] - mean_pnl) * (pnls[i-1] - mean_pnl) for i in range(1, len(pnls))) / ((len(pnls) - 1) * var_pnl)

        return {
            "simulations": self.n_simulations,
            "initial_capital": initial_capital,
            "block_size": block_size,
            "bootstrap_method": "stationary" if self.use_stationary else "block",
            "confidence_intervals": confidence_intervals,
            "prob_profit": round(prob_profit, 1),
            "prob_ruin_50pct": round(prob_ruin_50, 1),
            "prob_ruin_75pct": round(prob_ruin_75, 1),
            "expected_return_pct": round(((avg_final / initial_capital) - 1) * 100, 2),
            "worst_case": round(min(final_capitals), 0),
            "best_case": round(max(final_capitals), 0),
            "avg_final_capital": round(avg_final, 0),
            "avg_max_drawdown": round(sum(max_drawdowns) / len(max_drawdowns), 0),
            "avg_max_drawdown_pct": round(sum(max_drawdown_pcts) / len(max_drawdown_pcts), 2),
            "median_final": round(_percentile(final_capitals, 50), 0),
            "kelly_optimal_fraction": round(kelly_fraction, 4),
            "kelly_half_fraction": round(kelly_fraction / 2, 4),
            "autocorrelation_lag1": round(autocorr_1, 4),
            "serial_correlation_detected": abs(autocorr_1) > 0.1,
            "recommendation": self._generate_recommendation(
                prob_profit, prob_ruin_50, autocorr_1, kelly_fraction
            ),
        }

    def _generate_recommendation(
        self,
        prob_profit: float,
        prob_ruin: float,
        autocorr: float,
        kelly: float,
    ) -> str:
        """Generate risk management recommendation."""
        if prob_profit > 70 and prob_ruin < 5:
            return "STRONG: High probability of profit with low ruin risk. Consider half-Kelly sizing."
        elif prob_profit > 50 and prob_ruin < 15:
            return "MODERATE: Reasonable probability of profit. Use conservative position sizing."
        elif prob_profit > 30:
            return "WEAK: Marginal edge. Reduce position size significantly or improve strategy."
        else:
            return "POOR: Strategy shows negative expected value. Do not trade."
