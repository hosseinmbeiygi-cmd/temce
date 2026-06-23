from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from backtesting.types import BacktestResult, EquityPoint, FillEvent
from domain.common.enum_types import OrderSide


@dataclass
class ChartData:
    """Prepared data for rendering charts."""
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    drawdown_curve: list[dict[str, Any]] = field(default_factory=list)
    monthly_returns: list[dict[str, Any]] = field(default_factory=list)
    trade_pnl_distribution: list[dict[str, Any]] = field(default_factory=list)
    underwater_plot: list[dict[str, Any]] = field(default_factory=list)
    rolling_sharpe: list[dict[str, Any]] = field(default_factory=list)
    rolling_volatility: list[dict[str, Any]] = field(default_factory=list)
    alpha_correlation: list[dict[str, Any]] = field(default_factory=list)
    sector_exposure: list[dict[str, Any]] = field(default_factory=list)
    summary_metrics: dict[str, Any] = field(default_factory=dict)


class VisualizationEngine:
    """Prepares backtest results for visualization (chart-ready data).

    Designed to be framework-agnostic:
    - Outputs dict data that can be rendered by any charting library
    - Works with Plotly, ECharts, TradingView, or custom React components
    - All calculations use numpy for performance
    - Handles edge cases (empty data, single points, extreme values)

    Usage:
        engine = VisualizationEngine()
        chart = engine.prepare(result)
        # Send chart.equity_curve to frontend
        # Send chart.drawdown_curve to frontend
    """

    def prepare(self, result: BacktestResult) -> ChartData:
        """Convert a BacktestResult into chart-ready data."""
        chart = ChartData()
        chart.summary_metrics = self._extract_metrics(result)
        chart.equity_curve = self._build_equity_curve(result.equity_curve)
        chart.drawdown_curve = self._build_drawdown_curve(result.equity_curve)
        chart.underwater_plot = self._build_underwater(result.equity_curve)
        chart.monthly_returns = self._build_monthly_returns(result.equity_curve)
        chart.trade_pnl_distribution = self._build_trade_distribution(result.trades)
        chart.rolling_sharpe = self._build_rolling_sharpe(result.equity_curve)
        chart.rolling_volatility = self._build_rolling_volatility(result.equity_curve)
        return chart

    def _extract_metrics(self, result: BacktestResult) -> dict[str, Any]:
        navs = [p.nav for p in result.equity_curve]
        returns: list[float] = []
        for i in range(1, len(navs)):
            if navs[i - 1] > 0:
                returns.append((navs[i] - navs[i - 1]) / navs[i - 1])

        return {
            "initial_capital": result.initial_capital,
            "final_capital": result.final_capital,
            "total_return": result.total_return,
            "total_return_pct": result.total_return_pct,
            "total_trades": result.total_trades,
            "total_events": result.metadata.get("event_count", 0),
            "start_date": str(result.equity_curve[0].timestamp) if result.equity_curve else "",
            "end_date": str(result.equity_curve[-1].timestamp) if result.equity_curve else "",
            "mean_return": float(np.mean(returns)) if returns else 0.0,
            "std_return": float(np.std(returns)) if returns else 0.0,
            "min_return": float(np.min(returns)) if returns else 0.0,
            "max_return": float(np.max(returns)) if returns else 0.0,
        }

    def _build_equity_curve(self, points: list[EquityPoint]) -> list[dict[str, Any]]:
        if not points:
            return []
        start_nav = points[0].nav
        return [
            {
                "timestamp": str(p.timestamp),
                "nav": p.nav,
                "cash": p.cash,
                "positions_value": p.positions_value,
                "return_pct": ((p.nav / start_nav) - 1) * 100 if start_nav > 0 else 0.0,
            }
            for p in points
        ]

    def _build_drawdown_curve(self, points: list[EquityPoint]) -> list[dict[str, Any]]:
        if not points:
            return []
        peak = points[0].nav
        dd_points: list[dict[str, Any]] = []
        for p in points:
            if p.nav > peak:
                peak = p.nav
            dd = (p.nav - peak) / peak * 100 if peak > 0 else 0.0
            dd_points.append({"timestamp": str(p.timestamp), "drawdown_pct": dd})
        return dd_points

    def _build_underwater(self, points: list[EquityPoint]) -> list[dict[str, Any]]:
        """Build underwater plot data (drawdown as positive depth)."""
        dd = self._build_drawdown_curve(points)
        return [{"timestamp": d["timestamp"], "depth_pct": abs(d["drawdown_pct"])} for d in dd]

    def _build_monthly_returns(self, points: list[EquityPoint]) -> list[dict[str, Any]]:
        if len(points) < 2:
            return []
        monthly: dict[str, list[float]] = {}
        for i in range(1, len(points)):
            prev = points[i - 1]
            curr = points[i]
            month_key = curr.timestamp.strftime("%Y-%m")
            ret = (curr.nav - prev.nav) / prev.nav * 100 if prev.nav > 0 else 0.0
            if month_key not in monthly:
                monthly[month_key] = []
            monthly[month_key].append(ret)

        return [
            {"month": k, "return_pct": float(np.sum(v)), "n_observations": len(v)}
            for k, v in sorted(monthly.items())
        ]

    def _build_trade_distribution(self, trades: list[FillEvent]) -> list[dict[str, Any]]:
        if not trades:
            return []
        pnls: list[float] = []
        for t in trades:
            pnl = t.quantity * t.price
            if t.side == OrderSide.SELL:
                pnl = -pnl
            pnls.append(pnl)

        if not pnls:
            return []

        pnl_arr = np.array(pnls)
        return [
            {
                "mean": float(np.mean(pnl_arr)),
                "std": float(np.std(pnl_arr)),
                "min": float(np.min(pnl_arr)),
                "max": float(np.max(pnl_arr)),
                "median": float(np.median(pnl_arr)),
                "positive": int(np.sum(pnl_arr > 0)),
                "negative": int(np.sum(pnl_arr < 0)),
                "total": len(pnl_arr),
                "histogram": self._build_histogram(pnl_arr),
            }
        ]

    def _build_histogram(self, values: np.ndarray, n_bins: int = 20) -> list[dict[str, Any]]:
        if len(values) < 2:
            return [{"bin": 0, "count": len(values)}]
        counts, edges = np.histogram(values, bins=n_bins)
        return [
            {"bin_start": float(edges[i]), "bin_end": float(edges[i + 1]), "count": int(c)}
            for i, c in enumerate(counts)
        ]

    def _build_rolling_sharpe(self, points: list[EquityPoint], window: int = 60, risk_free_rate: float = 0.0) -> list[dict[str, Any]]:
        if len(points) < window + 1:
            return []
        navs = [p.nav for p in points]
        returns = [(navs[i] - navs[i - 1]) / navs[i - 1] for i in range(1, len(navs))]
        rolling: list[dict[str, Any]] = []
        for i in range(window, len(returns)):
            chunk = returns[i - window:i]
            mu = float(np.mean(chunk))
            sigma = float(np.std(chunk))
            excess_return = mu - risk_free_rate / 252.0  # Convert annual RF to daily
            sharpe = excess_return / sigma * np.sqrt(252) if sigma > 0 else 0.0
            rolling.append({
                "timestamp": str(points[i + 1].timestamp) if i + 1 < len(points) else "",
                "sharpe": sharpe,
            })
        return rolling

    def _build_rolling_volatility(self, points: list[EquityPoint], window: int = 20) -> list[dict[str, Any]]:
        if len(points) < window + 1:
            return []
        navs = [p.nav for p in points]
        returns = [(navs[i] - navs[i - 1]) / navs[i - 1] for i in range(1, len(navs))]
        rolling: list[dict[str, Any]] = []
        for i in range(window, len(returns)):
            chunk = returns[i - window:i]
            vol = float(np.std(chunk) * np.sqrt(252) * 100)
            rolling.append({
                "timestamp": str(points[i + 1].timestamp) if i + 1 < len(points) else "",
                "volatility_pct": vol,
            })
        return rolling

    def correlation_matrix(self, alpha_returns: dict[str, list[float]]) -> dict[str, Any]:
        """Build correlation matrix data for a set of alpha returns.

        Args:
            alpha_returns: {alpha_id: [list of returns]}

        Returns:
            Dict with 'alphas', 'matrix' (2D list), 'min', 'max'
        """
        names = list(alpha_returns.keys())
        n = len(names)
        if n < 2:
            return {"alphas": names, "matrix": [[1.0]], "min": 1.0, "max": 1.0}

        returns_arr = np.array([alpha_returns[name] for name in names])
        corr = np.corrcoef(returns_arr)

        return {
            "alphas": names,
            "matrix": corr.tolist(),
            "min": float(np.min(corr)),
            "max": float(np.max(corr)),
        }
