from __future__ import annotations

import numpy as np

from backtesting.types import BacktestResult


class RiskMetrics:
    @staticmethod
    def compute(result: BacktestResult, risk_free_rate: float = 0.0) -> dict[str, float]:
        metrics: dict[str, float] = {}
        navs = [p.nav for p in result.equity_curve]
        if len(navs) < 2:
            return {"volatility": 0.0, "sharpe_ratio": 0.0, "sortino_ratio": 0.0}
        returns = np.diff(navs) / navs[:-1]
        # BUG FIX #20: Use sample std (ddof=1) for financial return series
        vol = float(np.std(returns, ddof=1) * np.sqrt(252)) if len(returns) > 1 else 0.0
        metrics["volatility"] = vol
        avg_ret = float(np.mean(returns)) * 252
        excess_ret = avg_ret - risk_free_rate
        metrics["sharpe_ratio"] = excess_ret / vol if vol > 0 else 0.0
        downside = returns[returns < 0]
        downside_vol = float(np.std(downside, ddof=1) * np.sqrt(252)) if len(downside) > 1 else 1.0
        metrics["sortino_ratio"] = avg_ret / downside_vol if downside_vol > 0 else 0.0

        # Get max_drawdown from metrics dict (computed by DrawdownMetrics)
        max_dd_pct = result.metrics.get("max_drawdown", 0.0) if result.metrics else 0.0
        # BUG FIX #9: Calmar ratio - max_drawdown is already a percentage
        metrics["calmar_ratio"] = avg_ret / abs(max_dd_pct) if max_dd_pct != 0 else 0.0

        var_95 = float(np.percentile(returns, 5)) if len(returns) > 0 else 0.0
        metrics["var_95"] = var_95
        cvar_95 = (
            float(returns[returns <= var_95].mean()) if len(returns) > 0 and np.sum(returns <= var_95) > 0 else 0.0
        )
        metrics["cvar_95"] = cvar_95
        metrics["downside_volatility"] = downside_vol
        metrics["risk_free_return"] = risk_free_rate

        # BUG FIX #10: Omega ratio - clamp to avoid inf
        threshold = risk_free_rate / 252
        gains = float(np.sum(returns[returns > threshold] - threshold))
        losses = float(np.sum(threshold - returns[returns <= threshold]))
        metrics["omega_ratio"] = gains / losses if losses > 0 else 9999.0

        # Tail ratio
        tail_gain = float(np.percentile(returns, 95)) if len(returns) > 0 else 0.0
        tail_loss_raw = float(np.percentile(returns, 5)) if len(returns) > 0 else 0.0
        tail_loss = abs(tail_loss_raw)
        # BUG FIX #11: Handle all-positive returns case
        if tail_loss == 0:
            metrics["tail_ratio"] = 9999.0 if tail_gain > 0 else 0.0
        else:
            metrics["tail_ratio"] = tail_gain / tail_loss

        # Skewness and Kurtosis (BUG FIX #20: use ddof=1 for sample std)
        if len(returns) > 2:
            std_val = np.std(returns, ddof=1)
            if std_val > 0:
                metrics["skewness"] = float(((returns - np.mean(returns)) ** 3).mean() / (std_val ** 3))
                metrics["kurtosis"] = float(((returns - np.mean(returns)) ** 4).mean() / (std_val ** 4) - 3)
            else:
                metrics["skewness"] = 0.0
                metrics["kurtosis"] = 0.0
        else:
            metrics["skewness"] = 0.0
            metrics["kurtosis"] = 0.0

        # Pain index: average drawdown
        peak = navs[0]
        drawdowns = []
        for nav in navs:
            if nav > peak:
                peak = nav
            dd = (peak - nav) / peak if peak > 0 else 0
            drawdowns.append(dd)
        metrics["pain_index"] = float(np.mean(drawdowns)) if drawdowns else 0.0
        # BUG FIX #9: Recovery factor - consistent units (both in percentage)
        metrics["recovery_factor"] = float(np.sum(returns) * 100) / abs(max_dd_pct) if max_dd_pct != 0 else 0.0

        return metrics
