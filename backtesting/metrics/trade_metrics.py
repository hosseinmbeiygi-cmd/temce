from __future__ import annotations

import numpy as np

from backtesting.types import BacktestResult


class TradeMetrics:
    @staticmethod
    def compute(result: BacktestResult) -> dict[str, float]:
        metrics: dict[str, float] = {}
        trades = result.trades
        if not trades:
            return {"total_trades": 0, "win_rate": 0.0, "avg_profit": 0.0}
        metrics["total_trades"] = float(len(trades))
        buy_trades = [t for t in trades if t.side == "buy"]
        sell_trades = [t for t in trades if t.side == "sell"]
        metrics["buy_trades"] = float(len(buy_trades))
        metrics["sell_trades"] = float(len(sell_trades))
        profits = [t.price * t.quantity for t in trades]
        winning = [p for p in profits if p > 0]
        losing = [p for p in profits if p < 0]
        metrics["win_rate"] = (len(winning) / len(profits)) * 100 if profits else 0.0
        metrics["avg_profit"] = float(np.mean(profits)) if profits else 0.0
        metrics["avg_win"] = float(np.mean(winning)) if winning else 0.0
        metrics["avg_loss"] = float(np.mean(losing)) if losing else 0.0
        metrics["profit_factor"] = abs(sum(winning) / sum(losing)) if losing and sum(losing) != 0 else 0.0
        metrics["largest_win"] = float(max(profits)) if profits else 0.0
        metrics["largest_loss"] = float(min(profits)) if profits else 0.0
        metrics["avg_trade_duration"] = 0.0
        return metrics
