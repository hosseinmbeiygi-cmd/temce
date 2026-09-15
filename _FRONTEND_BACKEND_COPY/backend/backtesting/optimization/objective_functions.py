from __future__ import annotations

import numpy as np

from backtesting.types import BacktestResult


class ObjectiveFunctions:
    @staticmethod
    def maximize_sharpe(result: BacktestResult) -> float:
        navs = [p.nav for p in result.equity_curve]
        if len(navs) < 2:
            return -1e9
        returns = np.diff(navs) / navs[:-1]
        vol = np.std(returns)
        if vol == 0:
            return 0.0
        return float(np.mean(returns) / vol * np.sqrt(252))

    @staticmethod
    def minimize_drawdown(result: BacktestResult) -> float:
        navs = [p.nav for p in result.equity_curve]
        if len(navs) < 2:
            return 1e9
        running_max = np.maximum.accumulate(navs)
        drawdowns = (np.array(navs) - running_max) / running_max
        return -float(np.min(drawdowns)) * 100

    @staticmethod
    def maximize_return(result: BacktestResult) -> float:
        return result.total_return_pct

    @staticmethod
    def maximize_calmar(result: BacktestResult) -> float:
        navs = [p.nav for p in result.equity_curve]
        if len(navs) < 2:
            return -1e9
        returns = np.diff(navs) / navs[:-1]
        running_max = np.maximum.accumulate(navs)
        dd = float(np.min((np.array(navs) - running_max) / running_max))
        ann_return = float(np.mean(returns)) * 252
        return ann_return / abs(dd) if dd != 0 else 0.0

    @staticmethod
    def maximize_sortino(result: BacktestResult) -> float:
        navs = [p.nav for p in result.equity_curve]
        if len(navs) < 2:
            return -1e9
        returns = np.diff(navs) / navs[:-1]
        downside = returns[returns < 0]
        downside_vol = np.std(downside) if len(downside) > 1 else 1.0
        if downside_vol == 0:
            return 0.0
        return float(np.mean(returns) / downside_vol * np.sqrt(252))

    @staticmethod
    def combined_score(result: BacktestResult, weights: dict[str, float] | None = None) -> float:
        w = weights or {"sharpe": 0.4, "return": 0.3, "calmar": 0.3}
        score = 0.0
        score += w.get("sharpe", 0) * ObjectiveFunctions.maximize_sharpe(result)
        score += w.get("return", 0) * ObjectiveFunctions.maximize_return(result)
        score += w.get("calmar", 0) * ObjectiveFunctions.maximize_calmar(result)
        return score
