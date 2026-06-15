from __future__ import annotations

import numpy as np

from backtesting.types import BacktestResult


class BenchmarkMetrics:
    @staticmethod
    def compute(result: BacktestResult, benchmark_returns: list[float] | None = None) -> dict[str, float]:
        metrics: dict[str, float] = {}
        navs = [p.nav for p in result.equity_curve]
        if len(navs) < 2 or not benchmark_returns:
            return {"alpha": 0.0, "beta": 0.0, "tracking_error": 0.0}
        strat_returns = np.diff(navs) / navs[:-1]
        bm_returns = np.array(benchmark_returns[: len(strat_returns)])
        if len(bm_returns) < 2:
            return {"alpha": 0.0, "beta": 0.0, "tracking_error": 0.0}
        cov = np.cov(strat_returns, bm_returns)
        bm_var = np.var(bm_returns)
        metrics["beta"] = float(cov[0, 1] / bm_var) if bm_var > 0 else 1.0
        metrics["alpha"] = float(np.mean(strat_returns) - metrics["beta"] * np.mean(bm_returns)) * 252
        te = np.std(strat_returns - bm_returns) * np.sqrt(252)
        metrics["tracking_error"] = float(te)
        metrics["information_ratio"] = (
            float(np.mean(strat_returns - bm_returns) / np.std(strat_returns - bm_returns) * np.sqrt(252))
            if te > 0
            else 0.0
        )
        metrics["excess_return"] = float((np.prod(1 + strat_returns) - 1) - (np.prod(1 + bm_returns) - 1))
        return metrics
