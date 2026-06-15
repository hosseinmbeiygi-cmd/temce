from __future__ import annotations

import numpy as np

from backtesting.types import BacktestResult


class RiskMetrics:
    @staticmethod
    def compute(result: BacktestResult) -> dict[str, float]:
        metrics: dict[str, float] = {}
        navs = [p.nav for p in result.equity_curve]
        if len(navs) < 2:
            return {"volatility": 0.0, "sharpe_ratio": 0.0, "sortino_ratio": 0.0}
        returns = np.diff(navs) / navs[:-1]
        vol = float(np.std(returns) * np.sqrt(252))
        metrics["volatility"] = vol
        avg_ret = float(np.mean(returns)) * 252
        metrics["sharpe_ratio"] = avg_ret / vol if vol > 0 else 0.0
        downside = returns[returns < 0]
        downside_vol = float(np.std(downside) * np.sqrt(252)) if len(downside) > 0 else 1.0
        metrics["sortino_ratio"] = avg_ret / downside_vol if downside_vol > 0 else 0.0
        metrics["calmar_ratio"] = avg_ret / abs(result.max_drawdown / 100) if result.max_drawdown != 0 else 0.0
        var_95 = float(np.percentile(returns, 5)) if len(returns) > 0 else 0.0
        metrics["var_95"] = var_95
        cvar_95 = (
            float(returns[returns <= var_95].mean()) if len(returns) > 0 and np.sum(returns <= var_95) > 0 else 0.0
        )
        metrics["cvar_95"] = cvar_95
        metrics["downside_volatility"] = downside_vol
        metrics["risk_free_return"] = 0.0
        return metrics
