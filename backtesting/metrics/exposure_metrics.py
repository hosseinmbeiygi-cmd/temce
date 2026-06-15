from __future__ import annotations

from backtesting.types import BacktestResult


class ExposureMetrics:
    @staticmethod
    def compute(result: BacktestResult) -> dict[str, float]:
        metrics: dict[str, float] = {}
        trades = result.trades
        if not trades:
            return {"gross_exposure": 0.0, "net_exposure": 0.0, "avg_exposure": 0.0}
        total_long = sum(t.price * t.quantity for t in trades if t.side == "buy")
        total_short = sum(t.price * t.quantity for t in trades if t.side == "sell")
        avg_capital = (result.initial_capital + result.final_capital) / 2
        metrics["gross_exposure"] = (total_long + abs(total_short)) / avg_capital if avg_capital > 0 else 0.0
        metrics["net_exposure"] = (total_long - abs(total_short)) / avg_capital if avg_capital > 0 else 0.0
        metrics["long_exposure"] = total_long / avg_capital if avg_capital > 0 else 0.0
        metrics["short_exposure"] = abs(total_short) / avg_capital if avg_capital > 0 else 0.0
        metrics["avg_exposure"] = (metrics["long_exposure"] + metrics["short_exposure"]) / 2
        metrics["max_exposure"] = max(metrics["long_exposure"], metrics["short_exposure"])
        return metrics
