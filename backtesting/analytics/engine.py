from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from backtesting.types import BacktestResult


@dataclass
class AnalyticsResult:
    cagr: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    turnover: float = 0.0
    win_rate: float = 0.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    volatility: float = 0.0
    downside_volatility: float = 0.0
    calmar_ratio: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


class AnalyticsEngine:
    def compute(self, result: BacktestResult, trading_days: int = 252, risk_free_rate: float = 0.0) -> AnalyticsResult:
        ar = AnalyticsResult()
        navs = [p.nav for p in result.equity_curve]

        if len(navs) < 2:
            return ar

        ar.total_return = result.total_return
        ar.total_return_pct = result.total_return_pct

        self._compute_returns_metrics(ar, navs, trading_days, risk_free_rate)
        self._compute_drawdown(ar, navs)
        self._compute_trade_metrics(ar, result.trades)
        self._compute_turnover(ar, navs, result.trades)

        return ar

    def _compute_returns_metrics(self, ar: AnalyticsResult, navs: list[float], trading_days: int, risk_free_rate: float = 0.0) -> None:
        start_nav, end_nav = navs[0], navs[-1]
        years = len(navs) / trading_days
        if years > 0 and start_nav > 0:
            ar.cagr = (math.pow(end_nav / start_nav, 1.0 / years) - 1) * 100

        returns = [(navs[i] - navs[i - 1]) / navs[i - 1] for i in range(1, len(navs))]
        if not returns:
            return

        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        ar.volatility = math.sqrt(variance * trading_days) * 100
        annualized_return = mean_ret * trading_days
        # risk_free_rate is in decimal form (e.g. 0.05 for 5%)
        excess_return = annualized_return - risk_free_rate
        ar.sharpe_ratio = excess_return / (math.sqrt(variance) * math.sqrt(trading_days) or 1)

        downside = [r for r in returns if r < 0]
        if downside:
            down_var = sum((r - mean_ret) ** 2 for r in downside) / len(downside)
            ar.downside_volatility = math.sqrt(down_var * trading_days) * 100
            ar.sortino_ratio = (mean_ret * trading_days) / (ar.downside_volatility / 100 or 1)

    def _compute_drawdown(self, ar: AnalyticsResult, navs: list[float]) -> None:
        running_max = navs[0]
        max_dd = 0.0
        max_dd_pct = 0.0
        for nav in navs:
            if nav > running_max:
                running_max = nav
            dd = running_max - nav
            dd_pct = (dd / running_max) * 100 if running_max > 0 else 0
            if dd > max_dd:
                max_dd, max_dd_pct = dd, dd_pct
        ar.max_drawdown, ar.max_drawdown_pct = max_dd, max_dd_pct
        if max_dd_pct > 0 and ar.cagr != 0:
            ar.calmar_ratio = ar.cagr / max_dd_pct

    def _compute_trade_metrics(self, ar: AnalyticsResult, trades: list) -> None:
        ar.total_trades = len(trades)
        if not trades:
            return

        from collections import defaultdict
        open_positions: dict[str, list[float]] = defaultdict(list)
        round_trip_pnls: list[float] = []
        for t in sorted(trades, key=lambda x: x.timestamp):
            if t.side == "buy":
                open_positions[t.instrument_id].append(t.price)
            elif t.side == "sell" and open_positions.get(t.instrument_id):
                entry_price = open_positions[t.instrument_id].pop(0)
                pnl = (t.price - entry_price) * t.quantity - t.commission
                round_trip_pnls.append(pnl)

        if not round_trip_pnls:
            ar.win_rate = 0.0
            return

        wins = [p for p in round_trip_pnls if p > 0]
        losses = [p for p in round_trip_pnls if p <= 0]
        ar.winning_trades, ar.losing_trades = len(wins), len(losses)
        ar.win_rate = (len(wins) / len(round_trip_pnls)) * 100
        ar.avg_win = sum(wins) / len(wins) if wins else 0.0
        ar.avg_loss = sum(losses) / len(losses) if losses else 0.0
        ar.profit_factor = sum(wins) / max(abs(sum(losses)), 1.0)

    def _compute_turnover(self, ar: AnalyticsResult, navs: list[float], trades: list) -> None:
        if len(navs) > 1 and trades:
            total_traded_value = sum(t.price * t.quantity for t in trades)
            avg_nav = sum(navs) / len(navs)
            ar.turnover = total_traded_value / max(avg_nav, 1.0)
