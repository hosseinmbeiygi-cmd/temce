from __future__ import annotations

import numpy as np

from backtesting.types import BacktestResult


class DrawdownMetrics:
    @staticmethod
    def compute(result: BacktestResult) -> dict[str, float]:
        metrics: dict[str, float] = {}
        navs = [p.nav for p in result.equity_curve]
        if len(navs) < 2:
            return {"max_drawdown": 0.0, "avg_drawdown": 0.0, "drawdown_days": 0.0}
        running_max = np.maximum.accumulate(navs)
        drawdowns = (np.array(navs) - running_max) / running_max
        metrics["max_drawdown"] = float(np.min(drawdowns)) * 100
        metrics["avg_drawdown"] = float(np.mean(drawdowns)) * 100
        metrics["max_drawdown_duration"] = 0.0
        in_drawdown = drawdowns < 0
        transitions = np.diff(np.concatenate(([False], in_drawdown, [False])).astype(int))
        if np.any(transitions == -1):
            starts = np.where(transitions == 1)[0]
            ends = np.where(transitions == -1)[0]
            durations = ends[: len(starts)] - starts
            metrics["max_drawdown_duration"] = float(np.max(durations)) if len(durations) > 0 else 0.0
        metrics["drawdown_days"] = float(np.sum(in_drawdown))
        metrics["dd_pct_of_time"] = float(np.mean(in_drawdown) * 100)
        return metrics
