"""FIFO realized PnL must be net of commissions and reconcile with cash.

Before this fix ``PositionManager``/``PortfolioManager`` reported gross
realized PnL (expiry price difference only) while cash already paid the
buy and sell commissions — the ledger path was net, so the same trades
reported different PnL depending on which engine you asked.
"""

from __future__ import annotations

import pytest

from backtesting.metrics.trade_metrics import round_trip_pnls
from backtesting.types import FillEvent
from domain.common.enum_types import OrderSide


def _fill(side: str, qty: int, price: float, commission: float = 0.0) -> FillEvent:
    return FillEvent(
        order_id="t",
        instrument_id="X",
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        quantity=qty,
        price=price,
        commission=commission,
    )


def test_position_manager_realized_pnl_is_net_like_canonical() -> None:
    from backtesting.engine.position_manager import PositionManager

    trades = [
        _fill("buy", 100, 1000.0, 20.0),
        _fill("sell", 100, 1100.0, 25.0),
    ]
    pm = PositionManager()
    for t in trades:
        pm.update(t)

    expected = round_trip_pnls(trades)[0]
    assert expected == pytest.approx(9955.0)
    assert pm.get_total_realized_pnl() == pytest.approx(expected)


def test_position_manager_partial_lot_allocates_commissions() -> None:
    from backtesting.engine.position_manager import PositionManager

    trades = [
        _fill("buy", 100, 1000.0, 20.0),
        _fill("sell", 50, 1100.0, 25.0),
    ]
    pm = PositionManager()
    for t in trades:
        pm.update(t)

    # (1100-1000)*50 - 10 (half the buy commission) - 25 = 4965
    assert pm.get_total_realized_pnl() == pytest.approx(4965.0)
    pos = pm.get_position("X")
    assert pos.quantity == 50
    assert pos.lot_commissions == pytest.approx([10.0])


def test_portfolio_manager_realized_pnl_reconciles_with_cash() -> None:
    from backtesting.engine.portfolio import PortfolioManager

    pm = PortfolioManager()
    pm.reset(1_000_000.0)
    pm.update_fill_sync(_fill("buy", 100, 1000.0, 20.0))
    pm.update_fill_sync(_fill("sell", 100, 1100.0, 25.0))

    pos = pm.get_position("X")
    assert pos == 0
    # Flat position: cash movement is exactly the net realized PnL.
    assert pm.get_realized_pnl() == pytest.approx(9955.0)
    assert pm.get_cash() - 1_000_000.0 == pytest.approx(9955.0)


def test_split_preserves_total_commission() -> None:
    from backtesting.portfolio.manager import PortfolioManager

    pm = PortfolioManager()
    pm.reset(1_000_000.0)
    pm.update_fill_sync(_fill("buy", 100, 1000.0, 20.0))
    pm.adjust_positions("X", 2.0)
    pm.update_fill_sync(_fill("sell", 100, 600.0, 10.0))

    # Lot is now 200 shares @ 500 with the same 20 total commission:
    # (600-500)*100 - 20*(100/200) - 10 = 9980
    assert pm.get_realized_pnl() == pytest.approx(9980.0)


def test_realized_pnl_parity_across_engines() -> None:
    """The same trade must report one net PnL in every accounting path."""
    from datetime import date

    from backtesting.costs.iran_costs import IranTransactionCosts
    from backtesting.engine.portfolio import PortfolioManager
    from backtesting.engine.position_manager import PositionManager
    from backtesting.portfolio.ledger import PortfolioLedger

    price_buy, price_sell, qty = 1000.0, 1100.0, 100
    costs = IranTransactionCosts()
    buy_cost = costs.compute("buy", price_buy, qty)
    sell_cost = costs.compute("sell", price_sell, qty)

    trades = [
        _fill("buy", qty, price_buy, buy_cost),
        _fill("sell", qty, price_sell, sell_cost),
    ]
    canonical = round_trip_pnls(trades)[0]

    pm = PositionManager()
    for t in trades:
        pm.update(t)

    portfolio = PortfolioManager()
    portfolio.reset(1_000_000.0)
    for t in trades:
        portfolio.update_fill_sync(t)

    ledger = PortfolioLedger(initial_capital=1_000_000.0)
    ledger.buy("X", qty, price_buy, date(2026, 1, 1))
    ledger.sell("X", qty, price_sell, date(2026, 1, 2))

    assert canonical == pytest.approx(8_660.8)  # 10,000 - 371.2 - 968.0
    assert pm.get_total_realized_pnl() == pytest.approx(canonical)
    assert portfolio.get_realized_pnl() == pytest.approx(canonical)
    assert ledger.get_realized_pnl() == pytest.approx(canonical)
