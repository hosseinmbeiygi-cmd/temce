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
    recovery_factor: float = 0.0  # net profit / max_drawdown
    expectancy: float = 0.0  # (WR*avg_win - LR*|avg_loss|)  v1:24
    expectancy_pct: float = 0.0  # expectancy / avg entry cost
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    # significance (v2:103) - populated by bootstrap test
    expectancy_pvalue: float | None = None
    expectancy_ci_low: float | None = None
    expectancy_ci_high: float | None = None
    is_significant: bool | None = None
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

    def _compute_returns_metrics(
        self, ar: AnalyticsResult, navs: list[float], trading_days: int, risk_free_rate: float = 0.0
    ) -> None:
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
        excess_return = annualized_return - risk_free_rate
        ar.sharpe_ratio = excess_return / (math.sqrt(variance) * math.sqrt(trading_days) or 1) if variance > 0 else 0.0

        # Sortino: downside deviation vs target 0 (v2:104 - distinct for asymmetric returns)
        downside = [min(0, r) for r in returns]
        # use target 0, not mean, for proper Sortino
        down_var = sum(d**2 for d in downside) / len(returns)
        ar.downside_volatility = math.sqrt(down_var * trading_days) * 100
        if ar.downside_volatility > 0:
            ar.sortino_ratio = excess_return / (ar.downside_volatility / 100)
        else:
            ar.sortino_ratio = ar.sharpe_ratio if ar.sharpe_ratio != 0 else 0.0
            if all(r >= 0 for r in returns):
                ar.sortino_ratio = float("inf") if ar.sharpe_ratio > 0 else 0.0

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
        # Recovery factor: net profit / max_drawdown (v1:46)
        if max_dd > 0:
            ar.recovery_factor = ar.total_return / max_dd if ar.total_return else 0.0

    def _compute_trade_metrics(self, ar: AnalyticsResult, trades: list) -> None:
        ar.total_trades = len(trades)
        if not trades:
            return

        # FIFO cost-basis PnL (audit F4): the buy-side commission is included
        # in the round-trip PnL instead of only the sell commission.
        #   cost_basis = entry_price + buy_commission / buy_qty  (per share)
        #   pnl = (sell_price - cost_basis) * sell_qty - sell_commission
        # A deque is used for FIFO so opening a position is O(1), not O(n).
        from collections import defaultdict, deque

        open_positions: dict[str, deque] = defaultdict(deque)  # inst -> [(price, commission, qty)]
        round_trip_pnls: list[float] = []
        for t in sorted(trades, key=lambda x: x.timestamp):
            if t.side == "buy":
                open_positions[t.instrument_id].append((t.price, t.commission, t.quantity))
            elif t.side == "sell":
                positions = open_positions.get(t.instrument_id)
                remaining_sell = max(t.quantity, 0)
                sell_comm_per_unit = t.commission / max(t.quantity, 1)
                while positions and remaining_sell > 0:
                    entry_price, entry_commission, entry_quantity = positions.popleft()
                    matched_qty = min(entry_quantity, remaining_sell)
                    buy_comm_used = entry_commission * (matched_qty / max(entry_quantity, 1))
                    cost_basis = entry_price + buy_comm_used / max(matched_qty, 1)
                    pnl = (t.price - cost_basis) * matched_qty - sell_comm_per_unit * matched_qty
                    round_trip_pnls.append(pnl)
                    remaining_sell -= matched_qty
                    if entry_quantity > matched_qty:
                        positions.appendleft(
                            (
                                entry_price,
                                entry_commission - buy_comm_used,
                                entry_quantity - matched_qty,
                            )
                        )

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
        # Expectancy: (WR * avg_win) - (LR * |avg_loss|)  v1:24
        wr = len(wins) / len(round_trip_pnls) if round_trip_pnls else 0
        lr = 1 - wr
        ar.expectancy = wr * ar.avg_win - lr * abs(ar.avg_loss)
        # Bootstrap significance for expectancy (v2:103) - non-normal distribution
        try:
            from backtesting.analytics.significance import bootstrap_expectancy

            sig = bootstrap_expectancy(round_trip_pnls, n_bootstrap=2000)
            ar.expectancy_pvalue = sig["p_value"]
            ar.expectancy_ci_low = sig["ci_low"]
            ar.expectancy_ci_high = sig["ci_high"]
            ar.is_significant = sig["is_significant"]
            ar.extra["expectancy_bootstrap"] = sig
        except Exception:
            pass

    def _compute_turnover(self, ar: AnalyticsResult, navs: list[float], trades: list) -> None:
        if len(navs) > 1 and trades:
            total_traded_value = sum(t.price * t.quantity for t in trades)
            avg_nav = sum(navs) / len(navs)
            ar.turnover = total_traded_value / max(avg_nav, 1.0)
