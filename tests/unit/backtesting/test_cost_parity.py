"""Cost parity across ALL backtest fill paths (audit F2 guard).

Every fill-producing path in ``backtesting/`` must charge the canonical
Iranian transaction cost (:class:`backtesting.costs.iran_costs.IranTransactionCosts`)
for whatever it actually filled.

Guarantees:
- If a new path is added (or an existing one regresses) with a hardcoded
  ``commission=0.0``, the structural guard below fails — in CI and locally.
- If a path computes commission with a different formula, the parity tests
  fail with a clear diff.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backtesting.costs.iran_costs import IranTransactionCosts

CANONICAL = IranTransactionCosts()

PRICE = 2000.0
QTY = 100
SYMBOL = "فولاد"


# ── Helpers ─────────────────────────────────────────────────────────────────


def make_order(side: str):
    """A strategy-level Order (OrderSide enum side)."""
    from backtesting.execution.order_models import Order
    from domain.common.enum_types import OrderSide

    return Order(
        instrument_id=SYMBOL,
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        quantity=QTY,
        price=PRICE,
    )


def make_order_event(side: str):
    from backtesting.types import OrderEvent

    return OrderEvent(
        instrument_id=SYMBOL,
        side=side,
        quantity=QTY,
        price=PRICE,
        order_type="MARKET",
    )


def assert_fill_parity(fill, allow_none: bool = False) -> None:
    """Assert a fill carries exactly the canonical cost for what it filled."""
    if allow_none and fill is None:
        return
    assert fill is not None, "path produced no fill"
    expected = CANONICAL.compute(fill.side, fill.price, fill.quantity)
    assert fill.commission == pytest.approx(expected), (
        f"commission mismatch: got {fill.commission}, expected {expected} "
        f"for side={fill.side} price={fill.price} qty={fill.quantity}"
    )


# ── Per-path parity (parameterized over buy/sell) ───────────────────────────


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_fill_simulator_parity(side):
    from backtesting.execution.fill_simulator import FillSimulator

    fill = FillSimulator(fill_probability=1.0).simulate_fill(
        make_order(side), {"close": PRICE}
    )
    assert_fill_parity(fill)


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_market_execution_policy_parity(side):
    from backtesting.execution.execution_policy import MarketExecutionPolicy

    assert_fill_parity(MarketExecutionPolicy().execute(make_order(side), {"close": PRICE}))


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_limit_execution_policy_parity(side):
    from backtesting.execution.execution_policy import LimitExecutionPolicy

    md = {"high": PRICE + 10, "low": PRICE - 10}
    assert_fill_parity(LimitExecutionPolicy().execute(make_order(side), md))


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_partial_fill_parity(side):
    from backtesting.execution.partial_fill import PartialFillHandler

    fills = PartialFillHandler().process(make_order(side), available_liquidity=QTY * 10)
    assert fills
    assert_fill_parity(fills[0])


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_queue_simulation_parity(side):
    from backtesting.execution.queue_simulation import QueueSimulation

    qs = QueueSimulation(base_cancel_rate=0.0, base_trade_rate=1.0, lambda_coeff=0.1)
    qs.add_order(SYMBOL, is_buy=(side == "buy"), price=PRICE, quantity=QTY)
    fills = qs.simulate_step(SYMBOL, trade_volume=QTY, trade_price=PRICE)
    for fill in fills:
        assert_fill_parity(fill)


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_microstructure_queue_state_parity(side):
    from backtesting.microstructure.queue_state import QueueState, SimulatedOrder

    qs = QueueState()
    qs.add_order(
        SimulatedOrder(order_id="o1", side=side, price=PRICE, quantity=QTY, instrument_id=SYMBOL)
    )
    fills = qs.update_from_trade(trade_volume=QTY, trade_price=PRICE, side=side)
    for fill in fills:
        assert_fill_parity(fill)


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_broker_parity(side):
    """Main backtest path (BacktestSimulator/Broker) — compares against the
    fill's own execution price because Broker applies slippage."""
    from backtesting.engine.broker import Broker

    fill = Broker().submit_order_sync(make_order_event(side))
    assert fill is not None
    expected = CANONICAL.compute(side, fill.price, fill.quantity)
    assert fill.commission == pytest.approx(expected)


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_engine_execution_simulator_parity(side):
    """backtest_engine path (Engine ExecutionSimulator + CommissionModel)."""
    from backtesting.constants import SlippageMode
    from backtesting.engine.cash_manager import CashManager
    from backtesting.engine.commission import CommissionModel
    from backtesting.engine.execution_simulator import ExecutionSimulator
    from backtesting.engine.slippage import SlippageModel

    sim = ExecutionSimulator(
        slippage=SlippageModel(mode=SlippageMode.NONE),
        commission=CommissionModel(),  # default → canonical rates incl. clearing
    )
    cm = CashManager(initial_capital=1_000_000_000)
    fill = sim.execute(make_order_event(side), cm)
    assert fill is not None
    expected = CANONICAL.compute(side, fill.price, fill.quantity)
    assert fill.commission == pytest.approx(expected)


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_orders_manager_fallback_parity(side):
    """orders/manager force-fill path for MARKET orders when the fill
    simulator returns None (fill_probability=0)."""
    from backtesting.execution.fill_simulator import FillSimulator
    from backtesting.market.market_engine import MarketEngine
    from backtesting.orders.manager import OrderManager

    engine = MarketEngine()
    engine.add_instrument(SYMBOL, "tse")
    engine.update_quote(SYMBOL, bid=PRICE - 1, ask=PRICE + 1, bid_vol=1000, ask_vol=1000)

    om = OrderManager()
    om.submit(make_order_event(side))
    fills = om.process_pending(engine, FillSimulator(fill_probability=0.0))
    assert fills, "MARKET order should force-fill"
    assert_fill_parity(fills[0])


# ── Structural CI guard ─────────────────────────────────────────────────────


def test_no_hardcoded_free_fills_in_source():
    """CI guard (audit F2): no backtest fill path may hardcode commission=0.0.

    Add ``# parity-ok`` at the end of a line to explicitly allow a zero-cost
    fill (should be rare and deliberate).
    """
    repo_root = Path(__file__).resolve().parents[3]
    backtesting_dir = repo_root / "backtesting"

    offenders: list[str] = []
    for path in sorted(backtesting_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if "commission=0.0" in line and "# parity-ok" not in line:
                offenders.append(f"{path.relative_to(repo_root)}:{lineno}: {line.strip()}")

    assert not offenders, (
        "Hardcoded commission=0.0 found — fills must charge costs via "
        "cost_model.compute(...) so all backtest paths stay cost-consistent:\n"
        + "\n".join(offenders)
    )


def test_all_cost_classes_use_canonical_rates():
    """F1 guard: every active cost class defaults to the canonical rates."""
    from backtesting.engine.broker import CONSERVATIVE_COSTS, IRAN_MARKET_COSTS, Broker
    from backtesting.engine.commission import CommissionModel
    from backtesting.models.iran_costs import IranCommissionModel

    assert CommissionModel().broker_pct == CANONICAL.broker_pct
    assert CommissionModel().tax_pct == CANONICAL.sell_tax_pct
    assert CommissionModel().clearing_fee_pct == CANONICAL.clearing_fee_pct
    assert IranCommissionModel().broker_buy_pct == CANONICAL.broker_pct
    assert IranCommissionModel().clearing_fee_pct == CANONICAL.clearing_fee_pct
    assert IRAN_MARKET_COSTS.commission_pct == CANONICAL.broker_pct
    assert CONSERVATIVE_COSTS.commission_pct == CANONICAL.broker_pct
    assert Broker().cost_model.broker_pct == CANONICAL.broker_pct
