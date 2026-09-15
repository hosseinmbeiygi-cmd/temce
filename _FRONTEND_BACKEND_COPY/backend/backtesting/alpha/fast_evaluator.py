from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class AlphaMetrics:
    """Performance metrics for a single alpha signal."""

    sharpe: float = 0.0
    information_coefficient: float = 0.0
    t_stat: float = 0.0
    turnover: float = 0.0
    hit_rate: float = 0.0
    total_return: float = 0.0
    volatility: float = 0.0
    max_drawdown: float = 0.0
    is_valid: bool = False


class FastAlphaEvaluator:
    """Fast vectorized evaluation of alpha signals.

    Uses numpy operations for speed. Pre-filters alphas before
    expensive hybrid simulation testing.
    """

    def __init__(self, min_sharpe: float = 1.0, min_ic: float = 0.02, max_turnover: float = 1.0) -> None:
        self.min_sharpe = min_sharpe
        self.min_ic = min_ic
        self.max_turnover = max_turnover

    def evaluate(self, signal: list[float], returns: list[float]) -> AlphaMetrics:
        """Evaluate a single alpha signal against forward returns.

        Args:
            signal: Alpha signal values
            returns: Corresponding forward returns

        Returns:
            AlphaMetrics with performance statistics
        """
        metrics = AlphaMetrics()
        if len(signal) < 10 or len(returns) < 10:
            return metrics

        signal_arr = np.array(signal)
        returns_arr = np.array(returns)

        valid = np.isfinite(signal_arr) & np.isfinite(returns_arr)
        signal_arr = signal_arr[valid]
        returns_arr = returns_arr[valid]

        if len(signal_arr) < 10:
            return metrics

        # Forward lag: signal[t] predicts return[t+1]
        lagged_signal = signal_arr[:-1]
        forward_returns = returns_arr[1:]
        n = min(len(lagged_signal), len(forward_returns))
        lagged_signal = lagged_signal[:n]
        forward_returns = forward_returns[:n]

        if len(lagged_signal) < 10:
            return metrics

        # PnL from long/short
        pnl = lagged_signal * forward_returns

        # Sharpe ratio
        pnl_mean = float(np.mean(pnl))
        pnl_std = float(np.std(pnl))
        if pnl_std > 0:
            metrics.sharpe = pnl_mean / pnl_std * np.sqrt(252)
            metrics.t_stat = pnl_mean / pnl_std * np.sqrt(n)

        # Information Coefficient (correlation between signal and forward returns)
        if np.std(lagged_signal) > 0 and np.std(forward_returns) > 0:
            corr = np.corrcoef(lagged_signal, forward_returns)
            metrics.information_coefficient = float(corr[0, 1]) if corr.shape == (2, 2) else 0.0

        # Turnover (mean absolute change in signal)
        if len(lagged_signal) > 1:
            changes = np.abs(np.diff(lagged_signal))
            metrics.turnover = float(np.mean(changes))

        # Hit rate
        metrics.hit_rate = float(np.mean(pnl > 0))

        # Total return and volatility
        metrics.total_return = float(np.sum(pnl))
        metrics.volatility = pnl_std

        # Max drawdown
        cum_pnl = np.cumsum(pnl)
        running_max = np.maximum.accumulate(cum_pnl)
        drawdown = running_max - cum_pnl
        metrics.max_drawdown = float(np.max(drawdown))

        metrics.is_valid = (
            metrics.sharpe >= self.min_sharpe
            and abs(metrics.information_coefficient) >= self.min_ic
            and metrics.turnover <= self.max_turnover
        )

        return metrics

    def evaluate_batch(self, signals: dict[str, list[float]], returns: list[float]) -> dict[str, AlphaMetrics]:
        """Evaluate multiple alpha signals in batch.

        Args:
            signals: Dict of {alpha_id: signal_values}
            returns: Forward returns

        Returns:
            Dict of {alpha_id: AlphaMetrics}
        """
        results: dict[str, AlphaMetrics] = {}
        for alpha_id, signal in signals.items():
            results[alpha_id] = self.evaluate(signal, returns)
        return results

    def filter(self, signals: dict[str, list[float]], returns: list[float]) -> dict[str, AlphaMetrics]:
        """Evaluate and filter alphas, returning only passing metrics.

        Args:
            signals: Dict of {alpha_id: signal_values}
            returns: Forward returns

        Returns:
            Dict of passing {alpha_id: AlphaMetrics}
        """
        all_metrics = self.evaluate_batch(signals, returns)
        return {aid: m for aid, m in all_metrics.items() if m.is_valid}
