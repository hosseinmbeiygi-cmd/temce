"""Cross-consumer cost parity + explicit-tax identity (tasks 2-3).

Fixed scenario: PRICE=10_000, QTY=50, market=tse_equity
  buy  = 500_000 * 0.003712 = 1_856.0
  sell = 500_000 * 0.0088   = 4_400.0  (0.5% transfer tax INSIDE)
  tax part of sell = 500_000 * 0.005 = 2_500.0
Every consumer path must produce EXACTLY these numbers.
"""
import pytest

PRICE = 10_000.0
QTY = 50
PRINCIPAL = PRICE * QTY  # 500_000
MARKET = "tse_equity"
EXP_BUY = 1_856.0
EXP_SELL = 4_400.0
EXP_TAX = 2_500.0


def test_domain_helpers_match_table():
    from domain.trading import iran_costs as m

    assert m.buy_cost(PRICE, QTY) == pytest.approx(EXP_BUY)
    assert m.sell_cost(PRICE, QTY) == pytest.approx(EXP_SELL)
    assert m.sell_tax_cost(PRICE, QTY) == pytest.approx(EXP_TAX)
    assert m.compute("buy", PRICE, QTY) == pytest.approx(EXP_BUY)
    assert m.compute("sell", PRICE, QTY) == pytest.approx(EXP_SELL)


def test_explicit_tax_identity_all_markets():
    """buy_rate + sell_fee_rate + sell_tax == round_trip_rate (tax explicit
    yet inside sell — never added twice)."""
    from domain.trading import iran_costs as m

    for market in m.MARKET_RATES:
        if market.startswith("config:") or market.startswith("ledger-custom:"):
            continue
        b, s, t = m.buy_rate(market), m.sell_fee_rate(market), m.sell_tax(market)
        assert b + s + t == pytest.approx(m.round_trip_rate(market)), market
        assert s + m.sell_tax(market) == pytest.approx(m.sell_rate(market)), market


def test_engine_broker_parity():
    from backtesting.costs.iran_costs import IranTransactionCosts
    from backtesting.engine.broker import Broker, TransactionCostConfig
    from backtesting.types import OrderEvent, OrderSide

    b = Broker()
    canon = IranTransactionCosts()
    for side in ("buy", "sell"):
        o = OrderEvent(instrument_id="T", side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                       quantity=QTY, price=PRICE, daily_volume=10_000_000)
        f = b.submit_order_sync(o)
        # Broker charges commission on the slipped execution price — parity
        # holds against the canonical model AT THAT PRICE.
        assert f.commission == pytest.approx(canon.compute(side, f.price, f.quantity)), side
    # And at zero slippage the textbook numbers hold exactly:
    b0 = Broker(config=TransactionCostConfig(
        base_slippage_bps=0.0, min_slippage_bps=0.0, volume_impact_factor=0.0))
    for side, exp in (("buy", EXP_BUY), ("sell", EXP_SELL)):
        o = OrderEvent(instrument_id="T", side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                       quantity=QTY, price=PRICE, daily_volume=10_000_000)
        assert b0.submit_order_sync(o).commission == pytest.approx(exp), side


def test_engine_commission_model_parity():
    from backtesting.engine.commission import CommissionModel
    from backtesting.types import OrderEvent, OrderSide

    m = CommissionModel()
    for side, exp in (("buy", EXP_BUY), ("sell", EXP_SELL)):
        o = OrderEvent(instrument_id="T", side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                       quantity=QTY, price=PRICE)
        assert m.compute_for_order(o, PRICE, QTY) == pytest.approx(exp), side


def test_event_backtest_engine_parity():
    from services.event_backtest import ExecutionEngine

    e = ExecutionEngine()
    assert e.comm_buy * PRINCIPAL == pytest.approx(EXP_BUY)
    assert e.comm_sell * PRINCIPAL == pytest.approx(EXP_SELL)


def test_signal_backtest_engine_parity():
    from domain.trading.iran_costs import buy_rate, sell_rate
    from services.signal_backtest_engine import SignalBacktestEngine

    # This engine deducts one round-trip per trade — it must equal buy+sell.
    assert pytest.approx(buy_rate() + sell_rate()) == SignalBacktestEngine.TSE_ROUND_TRIP_COST_PCT
    assert pytest.approx(0.012512) == SignalBacktestEngine.TSE_ROUND_TRIP_COST_PCT


def test_rebalancer_parity():
    from backtesting.portfolio.rebalancer import RebalanceCost

    c = RebalanceCost()
    assert c.cost_for("buy", PRINCIPAL) == pytest.approx(EXP_BUY)
    assert c.cost_for("sell", PRINCIPAL) == pytest.approx(EXP_SELL)


def test_ledger_parity():
    from datetime import date

    from backtesting.portfolio.ledger import PortfolioLedger

    ledger = PortfolioLedger(initial_capital=10_000_000.0, settlement_days=0)
    buy_entry = ledger.buy("T", QTY, PRICE, date(2025, 1, 1))
    assert buy_entry.commission == pytest.approx(EXP_BUY)
    sell_entry = ledger.sell("T", QTY, PRICE, date(2025, 1, 1))
    assert sell_entry.commission == pytest.approx(EXP_SELL)
    assert sell_entry.tax == pytest.approx(0.0)  # inside commission, no double-count
