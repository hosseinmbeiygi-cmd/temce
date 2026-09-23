"""Signal Backtest Engine — backtests trading signals against historical market data.

Simulates entering/exiting positions based on signal directions and computes:
  - Win rate & accuracy by market/source
  - Profit factor, Sharpe ratio, max drawdown
  - Per-symbol performance breakdown
"""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import numpy as np

from core.db_utils import safe_row_str
from core.logging import get_logger
from core.result import PaginatedResult, Result
from services.signal_accuracy_tracker import SignalAccuracyTracker

logger = get_logger(__name__)


def _signal_anchor(signal: dict[str, Any]) -> date:
    """The date a signal was raised — the bar series must start *after* it.

    Without this the "future" query returns the symbol's oldest bars, so a signal
    raised today is scored against last year's price move.
    """

    for key in ("date", "signal_date", "created_at", "time", "timestamp"):
        raw = signal.get(key)
        if not raw:
            continue
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, date):
            return raw
        text = str(raw).strip().replace("/", "-")[:10]
        with contextlib.suppress(ValueError):
            return datetime.strptime(text, "%Y-%m-%d").date()
    return date.today()


@dataclass
class BacktestedSignal:
    """Result of backtesting a single signal against historical data."""
    signal_id: str
    symbol: str
    market: str
    source: str
    direction: str
    timeframe: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    return_pct: float
    correct: bool
    max_profit_pct: float
    max_loss_pct: float
    hit_target1: bool
    hit_target2: bool
    stopped_out: bool
    signal_score: float
    signal_confidence: float


@dataclass
class BacktestResult:
    """Aggregated backtest results for a set of signals."""
    total_signals: int = 0
    correct: int = 0
    accuracy_pct: float = 0.0
    total_return_pct: float = 0.0
    avg_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    sharpe: float = 0.0
    win_rate_pct: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    max_consecutive_losses: int = 0
    best_trade_pct: float = 0.0
    worst_trade_pct: float = 0.0
    by_market: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_source: dict[str, dict[str, Any]] = field(default_factory=dict)
    trades: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_signals": self.total_signals,
            "correct": self.correct,
            "accuracy_pct": round(self.accuracy_pct, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "avg_return_pct": round(self.avg_return_pct, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "profit_factor": round(self.profit_factor, 2),
            "sharpe": round(self.sharpe, 3),
            "win_rate_pct": round(self.win_rate_pct, 2),
            "avg_win_pct": round(self.avg_win_pct, 2),
            "avg_loss_pct": round(self.avg_loss_pct, 2),
            "max_consecutive_losses": self.max_consecutive_losses,
            "best_trade_pct": round(self.best_trade_pct, 2),
            "worst_trade_pct": round(self.worst_trade_pct, 2),
            "by_market": self.by_market,
            "by_source": self.by_source,
        }


class SignalBacktestEngine:
    """Backtests signals against historical price data to measure real performance.

    Transaction costs are deducted from each trade's return. Default costs:
        - stock: 0.3% round-trip (0.15% entry + 0.15% exit)
        - gold/currency/commodity: 0.5%
        - crypto: 0.5%
        - option: 1.0%
    """

    DEFAULT_TRANSACTION_COSTS = {
        "stock": 0.003,
        "gold": 0.005,
        "currency": 0.005,
        "crypto": 0.005,
        "commodity": 0.005,
        "option": 0.01,
        "ime": 0.005,
    }

    def __init__(self, session: Any = None) -> None:
        self._session = session
        self._tracker = SignalAccuracyTracker(session=session)

    async def backtest_signals(
        self,
        signals: list[dict[str, Any]],
        days_forward: int = 30,
        market: str | None = None,
        source: str | None = None,
    ) -> Result[BacktestResult]:
        """Backtest a list of signals against actual price movement.

        For each signal, fetches future price data (up to days_forward days)
        and evaluates whether the signal direction was correct.
        """
        try:

            from core.database import async_session_factory

            if async_session_factory is None:
                return Result.err("No database session available")

            async with async_session_factory() as session:
                outcomes: list[BacktestedSignal] = []

                for signal in signals:
                    symbol = signal.get("symbol", "")
                    market_type = signal.get("market", "stock")
                    signal.get("direction", "hold")
                    signal_price = signal.get("price", 0)
                    signal.get("timeframe", "daily")

                    if not symbol or not signal_price:
                        continue

                    if market and market_type != market:
                        continue
                    if source and signal.get("source") != source:
                        continue

                    # Fetch future price data
                    hist_data = await self._fetch_future_prices(
                        session, symbol, market_type, signal_price, days_forward,
                        from_date=_signal_anchor(signal),
                    )

                    if not hist_data:
                        continue

                    entry_price = hist_data[0].get("open", signal_price)
                    exit_price = hist_data[-1].get("close", signal_price)
                    high_prices = [h.get("high", exit_price) for h in hist_data]
                    low_prices = [h.get("low", entry_price) for h in hist_data]
                    max_high = max(high_prices) if high_prices else exit_price
                    min_low = min(low_prices) if low_prices else entry_price

                    # Parse targets/stop from signal
                    target1 = None
                    target2 = None
                    stop_loss = None
                    with contextlib.suppress(Exception):
                        targets_str = signal.get("targets", "")
                        if "هدف اول:" in targets_str:
                            numbers = re.findall(r"[\d,]+\.?\d*", targets_str.split("هدف اول:")[1].split("|")[0])
                            if numbers:
                                target1 = float(numbers[0].replace(",", ""))
                        if "هدف دوم:" in targets_str:
                            numbers = re.findall(r"[\d,]+\.?\d*", targets_str.split("هدف دوم:")[1])
                            if numbers:
                                target2 = float(numbers[0].replace(",", ""))
                        sl_str = signal.get("stop_loss", "")
                        if sl_str:
                            sl_numbers = re.findall(r"[\d,]+\.?\d*", sl_str)
                            if sl_numbers:
                                stop_loss = float(sl_numbers[0].replace(",", ""))

                    # Evaluate
                    outcome = await self._tracker.evaluate_signal(
                        signal,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        high_price=max_high,
                        low_price=min_low,
                        target1=target1,
                        target2=target2,
                        stop_loss=stop_loss,
                    )

                    # Record to DB
                    with contextlib.suppress(Exception):
                        await self._tracker.record_outcome(outcome)

                    # Apply transaction costs to the return
                    costs_pct = self.DEFAULT_TRANSACTION_COSTS.get(market_type, 0.003)
                    cost_adjusted_return = outcome.actual_return_pct - (costs_pct * 100)

                    outcomes.append(BacktestedSignal(
                        signal_id=outcome.signal_id,
                        symbol=outcome.symbol,
                        market=outcome.market,
                        source=outcome.source,
                        direction=outcome.direction,
                        timeframe=outcome.timeframe,
                        entry_date=hist_data[0].get("date", ""),
                        exit_date=hist_data[-1].get("date", ""),
                        entry_price=outcome.entry_price,
                        exit_price=outcome.exit_price,
                        return_pct=cost_adjusted_return,
                        correct=outcome.direction_correct,
                        max_profit_pct=outcome.max_profit_pct,
                        max_loss_pct=outcome.max_loss_pct,
                        hit_target1=outcome.hit_target1,
                        hit_target2=outcome.hit_target2,
                        stopped_out=outcome.stopped_out,
                        signal_score=outcome.signal_strength,
                        signal_confidence=outcome.signal_confidence,
                    ))

                # Aggregate results
                result = self._aggregate_results(outcomes)
                return Result.ok(result)

        except Exception as e:
            logger.error("Signal backtest failed: %s", e, exc_info=True)
            return Result.err(str(e))

    async def _fetch_future_prices(
        self,
        session: Any,
        symbol: str,
        market: str,
        current_price: float,
        days_forward: int,
        from_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch price bars strictly after the signal date.

        Filters on ``gregorian_date`` (a real DATE) rather than ``date`` — that column is
        a VARCHAR holding both Jalali and Gregorian strings, so a string comparison there
        silently selects the wrong window.
        """
        try:
            from sqlalchemy import text

            table_map = {
                "stock": "brsapi_historical_daily",
                "gold": "brsapi_gold_coin_history",
                "currency": "brsapi_currency_history",
                "crypto": "brsapi_gold_currency_pro_daily_history",
            }
            table = table_map.get(market, "brsapi_historical_daily")
            anchor = from_date or date.today()

            r = await session.execute(text(f"""
                SELECT gregorian_date, price_first as open, price_max as high,
                       price_min as low, price_close as close
                FROM {table}
                WHERE symbol = :symbol AND price_close > 0 AND gregorian_date > :from_date
                ORDER BY gregorian_date ASC
                LIMIT :days
            """), {"symbol": symbol, "from_date": anchor, "days": days_forward})
            rows = r.fetchall()

            return [
                {"date": safe_row_str(row, idx=0), "open": row[1] or current_price,
                 "high": row[2] or current_price, "low": row[3] or current_price,
                 "close": row[4] or current_price}
                for row in rows
            ]

        except Exception as e:
            logger.debug("Could not fetch future prices for %s: %s", symbol, e)
            return []

    def _aggregate_results(self, outcomes: list[BacktestedSignal]) -> BacktestResult:
        """Aggregate individual backtest results into summary statistics."""
        if not outcomes:
            return BacktestResult()

        result = BacktestResult(
            total_signals=len(outcomes),
            trades=[{
                "symbol": o.symbol, "market": o.market, "source": o.source,
                "direction": o.direction, "return_pct": round(o.return_pct, 2),
                "correct": o.correct, "entry_price": o.entry_price,
                "exit_price": o.exit_price,
                "max_profit_pct": round(o.max_profit_pct, 2),
                "max_loss_pct": round(o.max_loss_pct, 2),
                "entry_date": o.entry_date, "exit_date": o.exit_date,
            } for o in outcomes],
        )

        # Accuracy
        result.correct = sum(1 for o in outcomes if o.correct)
        result.accuracy_pct = (result.correct / max(result.total_signals, 1)) * 100

        # Returns
        returns = [o.return_pct for o in outcomes]
        result.total_return_pct = sum(returns)
        result.avg_return_pct = sum(returns) / max(len(returns), 1)

        # Win/Loss stats
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]
        result.win_rate_pct = (len(wins) / max(len(returns), 1)) * 100
        result.avg_win_pct = sum(wins) / max(len(wins), 1) if wins else 0
        result.avg_loss_pct = sum(losses) / max(len(losses), 1) if losses else 0

        # Best/Worst
        result.best_trade_pct = max(returns) if returns else 0
        result.worst_trade_pct = min(returns) if returns else 0

        # Max consecutive losses
        max_consec = 0
        current_consec = 0
        for o in outcomes:
            if not o.correct:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0
        result.max_consecutive_losses = max_consec

        # Profit factor
        total_profit = sum(wins) if wins else 0
        total_loss = sum(abs(loss) for loss in losses) if losses else 0
        result.profit_factor = total_profit / total_loss if total_loss > 0 else (float("inf") if total_profit > 0 else 0.0)

        # Sharpe ratio (annualized for daily returns: multiply by sqrt(252))
        if len(returns) > 1:
            mean_r = np.mean(returns)
            std_r = np.std(returns, ddof=1)
            period_sharpe = mean_r / max(std_r, 0.001)
            result.sharpe = period_sharpe * (252 ** 0.5)
        else:
            result.sharpe = 0.0

        # Max drawdown (compounding returns via cumprod)
        if returns:
            cumulative = np.cumprod(1.0 + np.array(returns) / 100.0)
            peak = np.maximum.accumulate(cumulative)
            drawdown = (peak - cumulative) / np.maximum(peak, 1e-10)
            result.max_drawdown_pct = float(np.max(drawdown)) * 100
        else:
            result.max_drawdown_pct = 0.0

        # By market
        markets = {o.market for o in outcomes}
        for m in markets:
            m_outcomes = [o for o in outcomes if o.market == m]
            m_correct = sum(1 for o in m_outcomes if o.correct)
            result.by_market[m] = {
                "total": len(m_outcomes),
                "correct": m_correct,
                "accuracy_pct": round((m_correct / max(len(m_outcomes), 1)) * 100, 2),
                "avg_return_pct": round(sum(o.return_pct for o in m_outcomes) / max(len(m_outcomes), 1), 2),
            }

        # By source
        sources = {o.source for o in outcomes}
        for s in sources:
            s_outcomes = [o for o in outcomes if o.source == s]
            s_correct = sum(1 for o in s_outcomes if o.correct)
            result.by_source[s] = {
                "total": len(s_outcomes),
                "correct": s_correct,
                "accuracy_pct": round((s_correct / max(len(s_outcomes), 1)) * 100, 2),
            }

        return result

    async def get_backtest_history(
        self,
        market: str | None = None,
        source: str | None = None,
        days: int = 90,
        page: int = 1,
        page_size: int = 50,
    ) -> Result[PaginatedResult[dict[str, Any]]]:
        """Get historical backtest results from the signal_accuracy table."""
        from services.signal_accuracy_tracker import SignalAccuracyTracker

        tracker = SignalAccuracyTracker(session=self._session)
        return await tracker.get_accuracy_by_market(
            market=market, days=days, page=page, page_size=page_size
        )
