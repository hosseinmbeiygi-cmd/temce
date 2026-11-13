from __future__ import annotations

import numpy as np

from backtesting.types import BacktestResult
from core.trading_constants import TRADING_DAYS_PER_YEAR_GLOBAL


class PerformanceMetrics:
    @staticmethod
    def compute(result: BacktestResult, risk_free_rate: float = 0.0) -> dict[str, float]:
        metrics: dict[str, float] = {}

        metrics["total_return"] = result.total_return
        metrics["total_return_pct"] = result.total_return_pct
        metrics["final_capital"] = result.final_capital

        navs = [p.nav for p in result.equity_curve]
        if len(navs) > 1:
            returns = np.diff(navs) / navs[:-1]
            # BT-M1: sample std (ddof=1) consistent with RiskMetrics
            metrics["volatility"] = float(np.std(returns, ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR_GLOBAL)) if len(returns) > 1 else 0.0
            avg_return = float(np.mean(returns)) * TRADING_DAYS_PER_YEAR_GLOBAL if len(returns) > 0 else 0.0
            vol = metrics["volatility"]
            excess_return = avg_return - risk_free_rate
            metrics["sharpe_ratio"] = excess_return / vol if vol > 0 else 0.0

            running_max = np.maximum.accumulate(navs)
            drawdowns = (navs - running_max) / running_max
            metrics["max_drawdown"] = float(np.min(drawdowns)) * 100

        if result.total_trades > 0:
            # BT-C1: win rate is computed on closing (sell) fills only; each
            # sell's net_pnl is the FIFO-realised gain net of all commissions.
            closing = [t for t in result.trades if t.side == "sell"]
            wins = sum(1 for t in closing if t.net_pnl > 0)
            denom = len(closing) if closing else result.total_trades
            metrics["win_rate"] = (wins / denom) * 100

        return metrics
