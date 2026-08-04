from __future__ import annotations

from datetime import datetime

import pytest

from backtesting.engine.portfolio import PortfolioManager
from backtesting.types import FillEvent
from domain.common.enum_types import OrderSide


def _make_fill(
    instrument_id: str, side: str, quantity: int, price: float, commission: float = 0.0,
) -> FillEvent:
    side_enum = OrderSide.BUY if side == "buy" else OrderSide.SELL
    return FillEvent(
        order_id=f"test_{datetime.now().isoformat()}",
        instrument_id=instrument_id,
        side=side_enum,
        quantity=quantity,
        price=price,
        commission=commission,
    )


class TestPortfolioMTM:
    def test_initial_state(self):
        pm = PortfolioManager()
        pm.reset(1_000_000_000)
        assert pm.get_cash() == 1_000_000_000
        assert pm.get_nav() == 1_000_000_000

    def test_fill_buy(self):
        pm = PortfolioManager()
        pm.reset(1_000_000_000)
        fill = _make_fill("IRAN123", "buy", 1000, 10000, 5000)
        pm.update_fill_sync(fill)
        assert pm.get_position("IRAN123") == 1000
        assert pm.get_cash() == 1_000_000_000 - 10_000_000 - 5000

    def test_fill_sell(self):
        pm = PortfolioManager()
        pm.reset(1_000_000_000)
        buy = _make_fill("IRAN123", "buy", 1000, 10000, 5000)
        pm.update_fill_sync(buy)
        sell = _make_fill("IRAN123", "sell", 500, 11000, 3000)
        pm.update_fill_sync(sell)
        assert pm.get_position("IRAN123") == 500
        # NAV should have increased: buy at 10k, sell at 11k
        expected_cash = 1_000_000_000 - 10_000_000 - 5000 + (11_000 * 500) - 3000
        expected_nav = expected_cash + 500 * 10000  # remaining 500 valued at avg_price
        assert pm.get_nav() == pytest.approx(expected_nav, rel=1e-3)

    def test_mark_to_market_sync(self):
        pm = PortfolioManager()
        pm.reset(1_000_000_000)
        fill = _make_fill("IRAN123", "buy", 1000, 10000, 0)
        pm.update_fill_sync(fill)
        pm.mark_to_market_sync({"IRAN123": 11000})
        assert pm.get_nav() > 1_000_000_000

    def test_position_adjustment(self):
        pm = PortfolioManager()
        pm.reset(1_000_000_000)
        fill = _make_fill("IRAN123", "buy", 1000, 10000)
        pm.update_fill_sync(fill)
        pm.adjust_positions("IRAN123", 2.0)
        assert pm.get_position("IRAN123") == 2000

    def test_positions_value(self):
        pm = PortfolioManager()
        pm.reset(1_000_000_000)
        fill = _make_fill("IRAN123", "buy", 1000, 10000)
        pm.update_fill_sync(fill)
        pm.mark_to_market_sync({"IRAN123": 11000})
        assert pm.get_positions_value() == 1000 * 11000

    def test_get_positions(self):
        pm = PortfolioManager()
        pm.reset(1_000_000_000)
        fill = _make_fill("IRAN123", "buy", 1000, 10000)
        pm.update_fill_sync(fill)
        positions = pm.get_positions()
        assert positions == {"IRAN123": 1000}
