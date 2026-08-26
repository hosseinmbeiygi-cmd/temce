"""Tests for the canonical Iranian transaction cost model.

Covers audit findings:
- F1: single source of truth for rates across cost classes.
- F2: fills produced by all backtest paths carry non-zero commission.
- F3: tax (0.5%) is charged on the SELL side only.
"""

from __future__ import annotations

import pytest

# ── F3: tax on sell side only ───────────────────────────────────────────────


def test_buy_has_no_tax():
    from backtesting.costs.iran_costs import IranTransactionCosts

    costs = IranTransactionCosts()
    price, qty = 1000.0, 100
    principal = price * qty
    buy = costs.compute("buy", price, qty)
    # Buy cost = broker + clearing only (no 0.5% tax component)
    assert buy == pytest.approx(principal * costs.broker_pct + principal * costs.clearing_fee_pct)


def test_sell_includes_tax():
    from backtesting.costs.iran_costs import IranTransactionCosts

    costs = IranTransactionCosts()
    price, qty = 1000.0, 100
    principal = price * qty
    sell = costs.compute("sell", price, qty)
    assert sell == pytest.approx(
        principal * costs.broker_pct + principal * costs.clearing_fee_pct + principal * costs.sell_tax_pct
    )


def test_sell_is_more_expensive_than_buy():
    from backtesting.costs.iran_costs import IranTransactionCosts

    costs = IranTransactionCosts()
    assert costs.compute("sell", 1000.0, 100) > costs.compute("buy", 1000.0, 100)


def test_round_trip_is_buy_plus_sell():
    from backtesting.costs.iran_costs import IranTransactionCosts

    costs = IranTransactionCosts()
    rt = costs.round_trip_cost(buy_price=1000.0, buy_qty=100, sell_price=1100.0, sell_qty=100)
    assert rt == pytest.approx(
        costs.compute("buy", 1000.0, 100) + costs.compute("sell", 1100.0, 100)
    )


def test_compute_accepts_enum_side():
    from backtesting.costs.iran_costs import IranTransactionCosts
    from domain.common.enum_types import OrderSide

    costs = IranTransactionCosts()
    assert costs.compute(OrderSide.BUY, 1000.0, 10) == costs.compute("buy", 1000.0, 10)
    assert costs.compute(OrderSide.SELL, 1000.0, 10) == costs.compute("sell", 1000.0, 10)


def test_canonical_rates_are_single_sourced():
    """F1: engine and broker defaults must match the canonical rates."""
    from backtesting.costs.iran_costs import BROKER_PCT, CLEARING_FEE_PCT, SELL_TAX_PCT
    from backtesting.engine.commission import CommissionModel
    from backtesting.models.iran_costs import IranCommissionModel

    assert CommissionModel().broker_pct == BROKER_PCT
    assert CommissionModel().tax_pct == SELL_TAX_PCT
    assert IranCommissionModel().broker_buy_pct == BROKER_PCT
    assert IranCommissionModel().broker_sell_pct == BROKER_PCT
    assert IranCommissionModel().tax_pct == SELL_TAX_PCT
    assert IranCommissionModel().clearing_fee_pct == CLEARING_FEE_PCT


# ── F3 regression: engine CommissionModel tax on sell only ────────────────


def _make_order(side: str):
    from backtesting.types import OrderEvent
    from core.ids import new_id

    return OrderEvent(
        instrument_id="خودرو",
        side=side,
        quantity=100,
        price=1000.0,
        order_type="MARKET",
        order_id=new_id("order"),
    )


def test_engine_commission_buy_has_no_tax():
    from backtesting.engine.commission import CommissionModel

    model = CommissionModel(iran_mode=False)  # default (non-iran) path
    order = _make_order("buy")
    total = model.compute_for_order(order, fill_price=1000.0, fill_qty=100)
    principal = 1000.0 * 100
    # Buy = broker + clearing, NO tax
    assert total == pytest.approx(principal * model.broker_pct + principal * model.clearing_fee_pct)


def test_engine_commission_sell_has_tax():
    from backtesting.engine.commission import CommissionModel

    model = CommissionModel(iran_mode=False)
    order = _make_order("sell")
    total = model.compute_for_order(order, fill_price=1000.0, fill_qty=100)
    principal = 1000.0 * 100
    # Sell = broker + clearing + tax
    assert total == pytest.approx(
        principal * model.broker_pct + principal * model.clearing_fee_pct + principal * model.tax_pct
    )


def test_engine_commission_iran_mode_buy_has_no_tax():
    from backtesting.engine.commission import CommissionModel
    from backtesting.models.iran_costs import IranCommissionModel

    model = CommissionModel(iran_mode=True)
    iran = IranCommissionModel()
    order = _make_order("buy")
    total = model.compute_for_order(order, fill_price=1000.0, fill_qty=100)
    # Iran buy = broker + clearing, no tax
    principal = 1000.0 * 100
    assert total == pytest.approx(
        principal * iran.broker_buy_pct + principal * iran.clearing_fee_pct
    )


# ── F2: fills are no longer free + cross-path parity ───────────────────────


def test_fill_simulator_charges_commission():
    from backtesting.execution.execution_policy import LimitExecutionPolicy, MarketExecutionPolicy
    from backtesting.execution.fill_simulator import FillSimulator
    from backtesting.execution.order_models import Order
    from backtesting.execution.partial_fill import PartialFillHandler
    from domain.common.enum_types import OrderSide

    order = Order(
        instrument_id="فولاد",
        side=OrderSide.BUY,
        quantity=100,
        price=2000.0,
    )
    market_data = {"close": 2000.0, "high": 2010.0, "low": 1990.0}

    fill = FillSimulator(fill_probability=1.0).simulate_fill(order, market_data)
    assert fill is not None
    assert fill.commission > 0

    fill2 = MarketExecutionPolicy().execute(order, market_data)
    assert fill2 is not None and fill2.commission > 0

    fill3 = LimitExecutionPolicy().execute(order, market_data)
    assert fill3 is not None and fill3.commission > 0

    fills4 = PartialFillHandler().process(order, available_liquidity=1000)
    assert fills4 and fills4[0].commission > 0


def test_cost_parity_across_paths():
    """F2 parity: the same order must cost the same everywhere."""
    from backtesting.costs.iran_costs import DEFAULT_IRAN_COSTS, IranTransactionCosts
    from backtesting.engine.broker import Broker

    price, qty = 2000.0, 100

    for side in ("buy", "sell"):
        canonical = IranTransactionCosts().compute(side, price, qty)
        broker = Broker(cost_model=DEFAULT_IRAN_COSTS)._compute_commission(
            exec_price=price, quantity=qty, side=side
        )
        assert broker == pytest.approx(canonical), f"Broker != canonical for {side}"


def test_broker_default_matches_canonical_rates():
    """F1: default Broker (main backtest path) uses the canonical rates."""
    from backtesting.costs.iran_costs import BROKER_PCT, SELL_TAX_PCT
    from backtesting.engine.broker import IRAN_MARKET_COSTS, Broker

    broker = Broker()
    assert broker.cost_model.broker_pct == BROKER_PCT
    assert broker.cost_model.sell_tax_pct == SELL_TAX_PCT
    assert IRAN_MARKET_COSTS.commission_pct == BROKER_PCT
    assert IRAN_MARKET_COSTS.sell_tax_pct == SELL_TAX_PCT


def test_queue_simulation_charges_commission():
    from backtesting.execution.queue_simulation import QueueSimulation

    qs = QueueSimulation()
    qs.add_order("خودرو", is_buy=True, price=1000.0, quantity=1000)
    fills = qs.simulate_step("خودرو", trade_volume=500, trade_price=1000.0)
    # Stochastic: if a fill happened it must carry commission.
    for f in fills:
        assert f.commission > 0
