from __future__ import annotations

import numpy as np

from backtesting.types import BacktestResult


class ReturnMetrics:
    @staticmethod
    def compute(result: BacktestResult) -> dict[str, float]:
        metrics: dict[str, float] = {}
        navs = [p.nav for p in result.equity_curve]
        if len(navs) < 2:
            return {"total_return": 0.0, "total_return_pct": 0.0}
        metrics["total_return"] = navs[-1] - navs[0]
        metrics["total_return_pct"] = ((navs[-1] / navs[0]) - 1) * 100 if navs[0] > 0 else 0.0
        returns = np.diff(navs) / navs[:-1]
        metrics["avg_return"] = float(np.mean(returns)) if len(returns) > 0 else 0.0
        metrics["avg_return_annual"] = float(np.mean(returns)) * 252 if len(returns) > 0 else 0.0
        metrics["cumulative_return"] = float(np.prod(1 + returns) - 1) if len(returns) > 0 else 0.0
        metrics["min_return"] = float(np.min(returns)) if len(returns) > 0 else 0.0
        metrics["max_return"] = float(np.max(returns)) if len(returns) > 0 else 0.0
        metrics["positive_days"] = float(np.sum(returns > 0)) if len(returns) > 0 else 0.0
        metrics["negative_days"] = float(np.sum(returns < 0)) if len(returns) > 0 else 0.0
        return metrics
