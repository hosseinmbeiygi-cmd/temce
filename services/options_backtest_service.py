"""Options backtest service — historical strategy evaluation with costs.

Pipeline: fetch historical candles → run a strategy (ATM long-call trades
with an entry filter) → settle each trade at expiry → build the equity
curve net of Iranian transaction costs → report Win Rate, Max Drawdown,
Sharpe Ratio and the equity curve itself.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from domain.options.pricing import black_scholes_call
from domain.trading import iran_costs as _costs

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class HistoryBar:
    date: str
    close: float


@dataclass(frozen=True)
class OptionTrade:
    entry_date: str
    expiry_date: str
    exit_date: str
    exit_reason: str  # "stop" | "target" | "expiry"
    strike: float
    premium: float
    payoff: float
    pnl_net: float
    underlying_entry: float
    underlying_expiry: float


@dataclass(frozen=True)
class BacktestMetrics:
    n_trades: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    annualized_return_pct: float
    avg_win: float
    avg_loss: float


@dataclass(frozen=True)
class BacktestReport:
    metrics: BacktestMetrics
    equity_curve: list[float]
    equity_dates: list[str]
    trades: list[OptionTrade] = field(default_factory=list)


# ── Strategies: entry filters over the close history ─────────────────────────

def momentum_filter(closes: Sequence[float], idx: int, lookback: int = 20) -> bool:
    """Enter when price is above its `lookback` simple moving average."""
    if idx < lookback or lookback <= 0:
        return False
    window = closes[idx - lookback:idx]
    if not window:
        return False
    return closes[idx] > sum(window) / len(window)


def always_enter(closes: Sequence[float], idx: int) -> bool:
    """Baseline: enter at every eligible bar (for benchmarks)."""
    return True


STRATEGIES: dict[str, Callable[[Sequence[float], int], bool]] = {
    "momentum": momentum_filter,
    "always": always_enter,
}


# ── Metrics ──────────────────────────────────────────────────────────────────

def _sharpe(trade_returns: Sequence[float], risk_free: float = 0.0) -> float:
    n = len(trade_returns)
    if n < 2:
        return 0.0
    mean = sum(trade_returns) / n
    var = sum((r - mean) ** 2 for r in trade_returns) / (n - 1)
    if var <= 0 or not math.isfinite(var):
        return 0.0
    return (mean - risk_free) / math.sqrt(var) * math.sqrt(TRADING_DAYS_PER_YEAR)


def _max_drawdown(equity: Sequence[float]) -> tuple[float, float]:
    peak = -math.inf
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = max(max_dd, peak - v)
    dd_pct = (max_dd / peak * 100.0) if peak and peak > 0 else 0.0
    return max_dd, dd_pct


# ── Service ──────────────────────────────────────────────────────────────────

class OptionsBacktestService:
    """Backtest ATM long-call strategies on historical closes."""

    def __init__(
        self,
        entry_filter: Callable[[Sequence[float], int], bool] | str = "momentum",
        days_to_expiry: int = 30,
        risk_free_rate: float = 0.25,
        sigma: float = 0.30,
        initial_capital: float = 100_000_000.0,
        contract_size: int = 1000,
        stop_loss_pct: float = 0.50,
        take_profit_pct: float = 1.00,
    ) -> None:
        if isinstance(entry_filter, str):
            if entry_filter not in STRATEGIES:
                raise ValueError(f"unknown strategy: {entry_filter!r} (known: {sorted(STRATEGIES)})")
            entry_filter = STRATEGIES[entry_filter]
        if days_to_expiry <= 0:
            raise ValueError("days_to_expiry must be positive")
        self._entry_filter = entry_filter
        self._dte = days_to_expiry
        self._r = risk_free_rate
        self._sigma = sigma
        self._capital = initial_capital
        self._size = contract_size
        self._stop_pct = stop_loss_pct
        self._target_pct = take_profit_pct

    async def fetch_history(
        self, symbol: str, limit: int = 500, session_factory: object = None
    ) -> list[HistoryBar]:
        """Load daily closes from ``brsapi_historical_daily`` (newest last)."""
        from sqlalchemy import text

        from core.database import async_session_factory

        factory = session_factory or async_session_factory
        if factory is None:
            raise RuntimeError("no async session factory available")
        async with factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT date, price_close FROM brsapi_historical_daily "
                        "WHERE symbol = :s ORDER BY date DESC LIMIT :n"
                    ),
                    {"s": symbol, "n": limit},
                )
            ).all()
        bars = [
            HistoryBar(date=str(r[0]), close=float(r[1]))
            for r in reversed(rows)
            if r[1] is not None and float(r[1]) > 0
        ]
        return bars

    def run(self, bars: Sequence[HistoryBar]) -> BacktestReport:
        """Execute the strategy over `bars` and return the full report."""
        closes = [b.close for b in bars]
        dates = [b.date for b in bars]
        t_years = self._dte / 365.0

        trades: list[OptionTrade] = []
        equity = [self._capital]
        equity_dates = [dates[0]] if dates else []

        i = 0
        n = len(bars)
        while i + self._dte < n:
            if not self._entry_filter(closes, i):
                i += 1
                continue
            s = closes[i]
            premium_per_share = black_scholes_call(s, s, t_years, self._r, self._sigma)
            cost_premium = premium_per_share * self._size
            fee_in = _costs.buy_cost(cost_premium, 1)
            stop_level = cost_premium * (1.0 - self._stop_pct)
            target_level = cost_premium * (1.0 + self._target_pct)
            # Walk forward: stop/target exits on daily BS revaluation, else expiry.
            exit_reason = "expiry"
            exit_idx = i + self._dte
            exit_value = max(closes[exit_idx] - s, 0.0) * self._size
            for j in range(i + 1, i + self._dte):
                t_rem = max((i + self._dte - j) / 365.0, 1e-6)
                theo = black_scholes_call(closes[j], s, t_rem, self._r, self._sigma) * self._size
                if theo <= stop_level:
                    exit_reason, exit_idx, exit_value = "stop", j, max(theo, 0.0)
                    break
                if theo >= target_level:
                    exit_reason, exit_idx, exit_value = "target", j, theo
                    break
            s_exp = closes[exit_idx]
            fee_out = _costs.sell_cost(max(exit_value, 0.0), 1) if exit_value > 0 else 0.0
            pnl = exit_value - cost_premium - fee_in - fee_out
            trades.append(
                OptionTrade(
                    entry_date=dates[i], expiry_date=dates[i + self._dte],
                    exit_date=dates[exit_idx], exit_reason=exit_reason,
                    strike=s, premium=cost_premium, payoff=exit_value, pnl_net=pnl,
                    underlying_entry=s, underlying_expiry=s_exp,
                )
            )
            equity.append(equity[-1] + pnl)
            equity_dates.append(dates[exit_idx])
            i = exit_idx + 1  # non-overlapping holding periods

        wins = [t.pnl_net for t in trades if t.pnl_net > 0]
        losses = [t.pnl_net for t in trades if t.pnl_net <= 0]
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
        years = max(len(equity_dates) / TRADING_DAYS_PER_YEAR, 1e-9)
        ann_ret = ((equity[-1] / self._capital) ** (1.0 / years) - 1.0) * 100.0 if equity[-1] > 0 else -100.0
        max_dd, max_dd_pct = _max_drawdown(equity)
        per_trade_ret = [t.pnl_net / self._capital for t in trades]
        metrics = BacktestMetrics(
            n_trades=len(trades),
            win_rate=(len(wins) / len(trades) * 100.0) if trades else 0.0,
            total_pnl=sum(t.pnl_net for t in trades),
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            sharpe_ratio=_sharpe(per_trade_ret),
            profit_factor=profit_factor if math.isfinite(profit_factor) else 0.0,
            annualized_return_pct=ann_ret if math.isfinite(ann_ret) else 0.0,
            avg_win=(sum(wins) / len(wins)) if wins else 0.0,
            avg_loss=(sum(losses) / len(losses)) if losses else 0.0,
        )
        return BacktestReport(
            metrics=metrics, equity_curve=equity,
            equity_dates=equity_dates, trades=trades,
        )
