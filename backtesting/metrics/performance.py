from __future__ import annotations

import numpy as np

from backtesting.types import BacktestResult


class PerformanceMetrics:
    @staticmethod
    def compute(result: BacktestResult) -> dict[str, float]:
        metrics: dict[str, float] = {}

        metrics["total_return"] = result.total_return
        metrics["total_return_pct"] = result.total_return_pct
        metrics["final_capital"] = result.final_capital

        navs = [p.nav for p in result.equity_curve]
        if len(navs) > 1:
            returns = np.diff(navs) / navs[:-1]
            metrics["volatility"] = float(np.std(returns) * np.sqrt(252)) if len(returns) > 0 else 0.0
            avg_return = float(np.mean(returns)) * 252 if len(returns) > 0 else 0.0
            vol = metrics["volatility"]
            metrics["sharpe_ratio"] = avg_return / vol if vol > 0 else 0.0

            running_max = np.maximum.accumulate(navs)
            drawdowns = (navs - running_max) / running_max
            metrics["max_drawdown"] = float(np.min(drawdowns)) * 100

        if result.total_trades > 0:
            wins = sum(1 for t in result.trades if t.price > 0)
            metrics["win_rate"] = (wins / result.total_trades) * 100

        return metrics
