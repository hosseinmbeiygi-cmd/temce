"""قرارداد W4-01: فروش باید موجودی را کم کند و FIFO را رعایت کند.

قرمز روی کد فعلی: ``record_trade`` quantity دارایی را کم نمی‌کند و
فروش بیش از موجودی را هم رد نمی‌کند. سبز شدن بعد از رفع.
"""

from __future__ import annotations

from datetime import datetime, UTC

import pytest

from src.gold_desk.portfolio import HoldingDeletedError, HoldingNotFoundError, record_trade


class _Holding:
    def __init__(self, *, id: int, symbol: str, quantity: float, buy_price: float, deleted_at=None):
        self.id = id
        self.symbol = symbol
        self.quantity = quantity
        self.buy_price = buy_price
        self.deleted_at = deleted_at


class _FakeSession:
    def __init__(self, holding=None):
        self.holding = holding
        self.added = []
        self.commits = 0
        self.refreshed = []

    async def get(self, _model, pk):
        if self.holding is not None and self.holding.id == pk:
            return self.holding
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshed.append(obj)


@pytest.fixture()
def session():
    holding = _Holding(id=1, symbol="IR_COIN_EMAMI", quantity=10.0, buy_price=100_000.0)
    return _FakeSession(holding=holding)


async def test_sell_reduces_holding_quantity(session):
    """فروش ۳ واحد quantity را ۱۰ → ۷ می‌کند (کد فعلی تغییر نمی‌دهد ⇒ قرمز)."""
    trade = await record_trade(
        session,
        symbol="IR_COIN_EMAMI",
        action="sell",
        quantity=3.0,
        price=110_000.0,
        amount_irt=330_000.0,
        holding_id=1,
    )
    assert trade.pnl_irt == pytest.approx(30_000.0)
    # کد فعلی quantity را کم نمی‌کند ⇒ این افیرم Falš است.
    assert session.holding.quantity == pytest.approx(7.0), (
        "record_trade باید quantity دارایی را پس از فروش کاهش دهد"
    )


async def test_sell_more_than_inventory_raises(session):
    """فروش بیش از موجودی خطای صریح می‌دهد (کد فعلی اجازه می‌دهد ⇒ قرمز)."""
    with pytest.raises(ValueError):
        await record_trade(
            session,
            symbol="IR_COIN_EMAMI",
            action="sell",
            quantity=20.0,  # بیشتر از ۱۰ موجود
            price=110_000.0,
            amount_irt=2_200_000.0,
            holding_id=1,
        )
