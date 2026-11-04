"""Cash-accounting invariants for ``BacktestEngine``.

A buy must debit the account exactly once: execution price × quantity plus
commission. ``ExecutionSimulator`` and ``PortfolioAccounting`` both touch the
cash balance, so this test pins the net effect rather than either layer.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backtesting.engine.backtest_engine import BacktestEngine
from backtesting.engine.commission import CommissionModel
from backtesting.engine.slippage import SlippageModel
from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from domain.common.enum_types import OrderSide

TS_SIGNAL = datetime(2026, 1, 5, tzinfo=UTC)
TS_FILL = datetime(2026, 1, 6, tzinfo=UTC)


class OneBuyStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(name="one_buy")
        self._sent = False

    def on_bar(self, bar):
        if self._sent:
            return []
        self._sent = True
        return [OrderEvent(instrument_id="SYM", side=OrderSide.BUY, quantity=1)]

    def reset(self) -> None:
        self._sent = False


class BuyThenOversellStrategy(BaseStrategy):
    """Buys 1 share, then tries to sell 5 — more than it holds."""

    def __init__(self) -> None:
        super().__init__(name="buy_then_oversell")
        self._step = 0

    def on_bar(self, bar):
        self._step += 1
        if self._step == 1:
            return [OrderEvent(instrument_id="SYM", side=OrderSide.BUY, quantity=1)]
        if self._step == 2:
            return [OrderEvent(instrument_id="SYM", side=OrderSide.SELL, quantity=5)]
        return []

    def reset(self) -> None:
        self._step = 0


def _bars(price: float = 100.0) -> list[dict]:
    return [
        {"timestamp": TS_SIGNAL, "open": price, "close": price, "prices": {"SYM": price}},
        {"timestamp": TS_FILL, "open": price, "close": price, "prices": {"SYM": price}},
    ]


def _three_bars(price: float = 100.0) -> list[dict]:
    return [
        {"timestamp": TS_SIGNAL, "open": price, "close": price, "prices": {"SYM": price}},
        {"timestamp": TS_FILL, "open": price, "close": price, "prices": {"SYM": price}},
        {"timestamp": datetime(2026, 1, 7, tzinfo=UTC), "open": price, "close": price, "prices": {"SYM": price}},
    ]


@pytest.mark.asyncio
async def test_buy_debits_cash_exactly_once():
    engine = BacktestEngine(
        initial_capital=10_000.0,
        commission=CommissionModel(broker_pct=0.0, clearing_fee_pct=0.0, tax_pct=0.0),
        slippage=SlippageModel(fixed_bps=0.0),
    )

    result = await engine.run(OneBuyStrategy(), _bars())

    assert len(result.trades) == 1
    assert engine.cash_manager.cash == pytest.approx(9_900.0), engine.cash_manager.get_cash_flow_history()


@pytest.mark.asyncio
async def test_nav_after_buy_equals_cash_plus_position_value():
    engine = BacktestEngine(
        initial_capital=10_000.0,
        commission=CommissionModel(broker_pct=0.0, clearing_fee_pct=0.0, tax_pct=0.0),
        slippage=SlippageModel(fixed_bps=0.0),
    )

    result = await engine.run(OneBuyStrategy(), _bars())

    last = result.equity_curve[-1]
    assert last.cash == pytest.approx(9_900.0)
    assert last.positions_value == pytest.approx(100.0)
    assert last.nav == pytest.approx(10_000.0)


@pytest.mark.asyncio
async def test_buy_commission_charged_once():
    engine = BacktestEngine(
        initial_capital=10_000.0,
        commission=CommissionModel(broker_pct=0.001, clearing_fee_pct=0.0, tax_pct=0.0),
        slippage=SlippageModel(fixed_bps=0.0),
    )

    result = await engine.run(OneBuyStrategy(), _bars())

    fill = result.trades[0]
    assert fill.commission == pytest.approx(0.1)
    assert engine.cash_manager.cash == pytest.approx(10_000.0 - 100.0 - 0.1)


@pytest.mark.asyncio
async def test_fill_is_timestamped_with_the_execution_bar():
    """A fill stamped with wall clock cannot be matched to its bar."""
    engine = BacktestEngine(
        initial_capital=10_000.0,
        commission=CommissionModel(broker_pct=0.0, clearing_fee_pct=0.0, tax_pct=0.0),
        slippage=SlippageModel(fixed_bps=0.0),
    )

    result = await engine.run(OneBuyStrategy(), _bars())

    assert result.trades[0].timestamp == TS_FILL


@pytest.mark.asyncio
async def test_unaffordable_buy_leaves_cash_untouched():
    engine = BacktestEngine(
        initial_capital=50.0,
        commission=CommissionModel(broker_pct=0.0, clearing_fee_pct=0.0, tax_pct=0.0),
        slippage=SlippageModel(fixed_bps=0.0),
    )

    result = await engine.run(OneBuyStrategy(), _bars())

    assert result.trades == []
    assert engine.cash_manager.cash == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_sell_cannot_credit_more_than_held():
    """Selling unheld shares would mint cash out of nothing."""
    engine = BacktestEngine(
        initial_capital=10_000.0,
        commission=CommissionModel(broker_pct=0.0, clearing_fee_pct=0.0, tax_pct=0.0),
        slippage=SlippageModel(fixed_bps=0.0),
    )

    result = await engine.run(BuyThenOversellStrategy(), _three_bars())

    # Bought 1 at 100, sold only what was held. Sells settle through the
    # canonical 1405 cost table, so the only leakage is its sell commission.
    from backtesting.costs.iran_costs import IranTransactionCosts

    sell_fee = float(IranTransactionCosts().compute("sell", 100.0, 1))
    assert result.trades[1].quantity == 1
    assert engine.cash_manager.cash == pytest.approx(10_000.0 - sell_fee), engine.cash_manager.get_cash_flow_history()
    assert engine.position_manager.get_position("SYM").quantity == 0
