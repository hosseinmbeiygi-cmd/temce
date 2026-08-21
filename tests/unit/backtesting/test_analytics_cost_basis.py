"""Tests for F4 — FIFO cost-basis round-trip PnL (audit finding F4).

Guards that:
  1. The buy-side commission is included in the round-trip PnL (previously only
     the sell commission was deducted in ``AnalyticsEngine._compute_trade_metrics``).
  2. FIFO pairing is O(1) via ``collections.deque`` (previously ``list.pop(0)``).
  3. ``TradeMetrics`` (the parallel metrics path) applies the same cost-basis
     rule, including proportional commission allocation on partial lots.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backtesting.analytics.engine import AnalyticsEngine
from backtesting.metrics.trade_metrics import TradeMetrics
from backtesting.types import BacktestResult, EquityPoint, FillEvent
from domain.common.enum_types import OrderSide

_T0 = datetime(2025, 1, 1, tzinfo=UTC)


def _fill(order_id: str, side: OrderSide, qty: int, price: float, commission: float, seq: int) -> FillEvent:
    return FillEvent(
        order_id=order_id,
        instrument_id="INST",
        side=side,
        quantity=qty,
        price=price,
        commission=commission,
        timestamp=_T0 + timedelta(minutes=seq),
    )


def _result(trades: list[FillEvent]) -> BacktestResult:
    nav = 1_000_000.0
    equity = [
        EquityPoint(timestamp=_T0 + timedelta(minutes=i), nav=nav, cash=nav, positions_value=0.0)
        for i in range(len(trades) + 1)
    ]
    return BacktestResult(
        strategy_name="test",
        initial_capital=nav,
        final_capital=nav,
        equity_curve=equity,
        trades=trades,
    )


class TestAnalyticsEngine:
    def test_buy_commission_is_included_in_round_trip_pnl(self) -> None:
        trades = [
            _fill("b1", OrderSide.BUY, 100, 1000.0, 20.0, 1),
            _fill("s1", OrderSide.SELL, 100, 1100.0, 25.0, 2),
        ]
        ar = AnalyticsEngine().compute(_result(trades))

        # cost_basis = 1000 + 20/100 = 1000.2
        # pnl = (1100 - 1000.2) * 100 - 25 = 9955
        assert ar.total_trades == 2
        assert ar.winning_trades == 1
        assert ar.losing_trades == 0
        assert ar.win_rate == pytest.approx(100.0)
        assert ar.avg_win == pytest.approx(9955.0)
        assert ar.profit_factor == pytest.approx(9955.0)

    def test_sell_loss_also_absorbs_buy_commission(self) -> None:
        trades = [
            _fill("b1", OrderSide.BUY, 100, 1000.0, 20.0, 1),
            _fill("s1", OrderSide.SELL, 100, 900.0, 25.0, 2),
        ]
        ar = AnalyticsEngine().compute(_result(trades))

        # cost_basis = 1000.2; pnl = (900 - 1000.2) * 100 - 25 = -10045
        assert ar.losing_trades == 1
        assert ar.avg_loss == pytest.approx(-10045.0)  # engine keeps the sign
        assert ar.profit_factor == pytest.approx(0.0)

    def test_fifo_matches_oldest_buy_lot(self) -> None:
        trades = [
            _fill("b1", OrderSide.BUY, 100, 100.0, 10.0, 1),   # cost basis 100.1
            _fill("b2", OrderSide.BUY, 100, 200.0, 10.0, 2),
            _fill("s1", OrderSide.SELL, 100, 150.0, 5.0, 3),
        ]
        ar = AnalyticsEngine().compute(_result(trades))

        # FIFO: pairs with b1 -> (150 - 100.1) * 100 - 5 = 4985
        assert ar.winning_trades == 1
        assert ar.avg_win == pytest.approx(4985.0)

    def test_fifo_uses_deque_across_many_opens(self) -> None:
        # Many alternating lots — must stay correct FIFO and complete in O(1)/lot.
        trades: list[FillEvent] = []
        for i in range(50):
            trades.append(_fill(f"b{i}", OrderSide.BUY, 10, 100.0 + i, 1.0, i))
        for i in range(50):
            trades.append(_fill(f"s{i}", OrderSide.SELL, 10, 200.0 + i, 1.0, 100 + i))

        ar = AnalyticsEngine().compute(_result(trades))
        assert ar.winning_trades == 50
        assert ar.win_rate == pytest.approx(100.0)


class TestTradeMetricsConsistency:
    def test_full_round_trip_matches_analytics_cost_basis(self) -> None:
        trades = [
            _fill("b1", OrderSide.BUY, 100, 1000.0, 20.0, 1),
            _fill("s1", OrderSide.SELL, 100, 1100.0, 25.0, 2),
        ]
        metrics = TradeMetrics.compute(_result(trades))

        # Same cost-basis rule as AnalyticsEngine: pnl = 9955
        assert metrics["total_pnl"] == pytest.approx(9955.0)
        assert metrics["win_rate"] == pytest.approx(100.0)

    def test_partial_lot_allocates_commissions_proportionally(self) -> None:
        # Buy 100 @ 1000 (comm 20). Sell 50 @ 1100 (comm 25), then 50 @ 1150 (comm 25).
        # Lot 1: buy_comm_used=10, cost_basis=1000.2, pnl=(1100-1000.2)*50 - 25 = 4965
        # Lot 2: buy_comm_used=10, cost_basis=1000.2, pnl=(1150-1000.2)*50 - 25 = 7465
        trades = [
            _fill("b1", OrderSide.BUY, 100, 1000.0, 20.0, 1),
            _fill("s1", OrderSide.SELL, 50, 1100.0, 25.0, 2),
            _fill("s2", OrderSide.SELL, 50, 1150.0, 25.0, 3),
        ]
        metrics = TradeMetrics.compute(_result(trades))

        assert metrics["total_pnl"] == pytest.approx(4965.0 + 7465.0)
        # All buy commission (20) and both sell commissions (25 + 25) were absorbed.
        assert metrics["win_rate"] == pytest.approx(100.0)
