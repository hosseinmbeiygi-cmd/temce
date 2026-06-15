from __future__ import annotations

from backtesting.types import BacktestResult


class TurnoverMetrics:
    @staticmethod
    def compute(result: BacktestResult) -> dict[str, float]:
        metrics: dict[str, float] = {}
        trades = result.trades
        if not trades:
            return {"total_turnover": 0.0, "avg_turnover_per_trade": 0.0}
        total_turnover = sum(t.price * t.quantity for t in trades)
        metrics["total_turnover"] = total_turnover
        metrics["avg_turnover_per_trade"] = total_turnover / len(trades)
        avg_capital = (result.initial_capital + result.final_capital) / 2
        metrics["turnover_ratio"] = total_turnover / avg_capital if avg_capital > 0 else 0.0
        metrics["monthly_turnover"] = total_turnover / max(len(result.equity_curve) / 21, 1)
        return metrics
