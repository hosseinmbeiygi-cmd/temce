from __future__ import annotations

import numpy as np


class ReturnMetrics:
    """Return metrics for backtesting performance calculations."""

    def calculate_total_return(self, initial_capital: float, final_value: float) -> float:
        if initial_capital == 0:
            return 0.0
        return ((final_value / initial_capital) - 1) * 100

    def calculate_annualized_return(self, total_return_pct: float, days: int) -> float:
        if days <= 0:
            return 0.0
        total_return_decimal = total_return_pct / 100.0
        annualized = ((1 + total_return_decimal) ** (365 / days) - 1) * 100
        return annualized

    def calculate_sharpe_ratio(self, returns: list[float], risk_free_rate: float = 0.0) -> float | None:
        if len(returns) < 2:
            return None
        returns_arr = np.array(returns)
        excess_returns = returns_arr - risk_free_rate
        if np.std(excess_returns) == 0:
            return None
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
        return float(sharpe)

    def calculate_max_drawdown(self, equity: list[float]) -> float:
        if len(equity) < 2:
            return 0.0
        equity_arr = np.array(equity)
        running_max = np.maximum.accumulate(equity_arr)
        drawdowns = (equity_arr - running_max) / running_max
        return float(np.min(drawdowns)) * 100

    def calculate_sortino_ratio(self, returns: list[float], risk_free_rate: float = 0.0) -> float | None:
        if len(returns) < 2:
            return None
        returns_arr = np.array(returns)
        excess_returns = returns_arr - risk_free_rate
        downside = excess_returns[excess_returns < 0]
        if len(downside) == 0 or np.std(downside) == 0:
            return None
        sortino = np.mean(excess_returns) / np.std(downside) * np.sqrt(252)
        return float(sortino)
