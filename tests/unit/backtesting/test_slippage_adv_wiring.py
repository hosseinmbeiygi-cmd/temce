"""Engine slippage must honour ADV for VOLUME_BASED mode.

``ExecutionSimulator`` never passed the order's ``daily_volume`` to the
slippage model, so the volume-impact branch (which needs ``adv > 0``) was
silently skipped and every order was priced as if it were infinitesimal.
"""

from __future__ import annotations

import pytest

from backtesting.constants import SlippageMode
from backtesting.engine.cash_manager import CashManager
from backtesting.engine.commission import CommissionModel
from backtesting.engine.execution_simulator import ExecutionSimulator
from backtesting.engine.slippage import SlippageModel
from backtesting.types import OrderEvent
from domain.common.enum_types import OrderSide


def _simulator() -> ExecutionSimulator:
    return ExecutionSimulator(
        SlippageModel(mode=SlippageMode.VOLUME_BASED, fixed_bps=10.0, volume_impact_pct=0.1),
        CommissionModel(broker_pct=0.0, clearing_fee_pct=0.0, tax_pct=0.0),
    )


def _order(daily_volume: int | None) -> OrderEvent:
    return OrderEvent(
        instrument_id="فولاد", side=OrderSide.BUY, quantity=1000, price=15_000.0,
        daily_volume=daily_volume,
    )


def test_volume_impact_applies_when_adv_is_set() -> None:
    fill = _simulator().execute(_order(daily_volume=5_000), CashManager(1_000_000_000.0))

    assert fill is not None
    # fixed 10bps = 15; 1000/5000 * 10% = 300 -> 315
    assert fill.price == pytest.approx(15_315.0)


def test_volume_impact_absent_without_adv() -> None:
    fill = _simulator().execute(_order(daily_volume=None), CashManager(1_000_000_000.0))

    assert fill is not None
    assert fill.price == pytest.approx(15_015.0)


def test_sell_uses_the_same_adv_impact() -> None:
    order = _order(daily_volume=5_000)
    order.side = OrderSide.SELL

    fill = _simulator().execute(order, CashManager(1_000_000_000.0))

    assert fill is not None
    assert fill.price == pytest.approx(15_000.0 - 315.0)
