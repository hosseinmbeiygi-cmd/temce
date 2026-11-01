"""فروش باید موجودی لات‌ها را کم کند و P&L را FIFO حساب کند (W4-01/W4-08/W4-09).

قبلاً ``record_trade`` فقط ردیف trade را می‌نوشت و ``quantity`` دارایی دست‌نخورده
می‌ماند؛ بنابراین پورتفوی پس از فروش همان تعداد قبل را نشان می‌داد.

این تست‌ها مسیر بدون DB را می‌سنجند: ``_record_sell_as_fifo`` همان الگوریتم
FIFO تولیدی را روی objectهای ساده اجرا می‌کند.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.gold_desk.portfolio import InsufficientHoldingError, _record_sell_as_fifo

T0 = datetime(2026, 1, 1)
T1 = datetime(2026, 2, 1)
SYMBOL = "IR_GOLD_18K"


def _lot(
    holding_id: int, quantity: float, buy_price: float, bought_at: datetime = T0
) -> SimpleNamespace:
    return SimpleNamespace(
        id=holding_id,
        symbol=SYMBOL,
        quantity=quantity,
        buy_price=buy_price,
        buy_amount_irt=quantity * buy_price,
        bought_at=bought_at,
        deleted_at=None,
        user_id=None,
    )


async def test_partial_sell_decrements_quantity_and_cost_basis() -> None:
    lot = _lot(1, quantity=2.0, buy_price=50_000_000.0)

    trade = await _record_sell_as_fifo(
        lot=lot,
        symbol=SYMBOL,
        quantity=1.0,
        price=60_000_000.0,
        amount_irt=60_000_000.0,
    )

    assert lot.quantity == pytest.approx(1.0)
    assert lot.buy_amount_irt == pytest.approx(50_000_000.0)
    assert lot.deleted_at is None
    assert trade.action == "sell"
    assert trade.quantity == pytest.approx(1.0)
    assert trade.holding_id == 1
    assert trade.fee_irt == 0.0
    # 60M proceeds against the 50M FIFO cost of the one unit sold.
    assert trade.pnl_irt == pytest.approx(10_000_000.0)


async def test_fifo_consumes_oldest_lot_first_and_keeps_remainder_cost() -> None:
    oldest = _lot(1, quantity=1.0, buy_price=50_000_000.0, bought_at=T0)
    newer = _lot(2, quantity=1.0, buy_price=60_000_000.0, bought_at=T1)

    trade = await _record_sell_as_fifo(
        lots=[newer, oldest],  # input order must not matter; FIFO sorts by bought_at
        symbol=SYMBOL,
        quantity=1.5,
        price=70_000_000.0,
        amount_irt=105_000_000.0,
    )

    assert oldest.quantity == 0.0
    assert oldest.buy_amount_irt == 0.0
    assert oldest.deleted_at is not None
    assert newer.quantity == pytest.approx(0.5)
    assert newer.buy_amount_irt == pytest.approx(30_000_000.0)
    assert newer.deleted_at is None
    assert trade.holding_id is None  # multi-lot sale is not tied to one row
    # 50M from the oldest + 30M from the newer lot, against 105M proceeds.
    assert trade.pnl_irt == pytest.approx(25_000_000.0)


async def test_full_sell_soft_deletes_lot_and_deducts_fee() -> None:
    lot = _lot(7, quantity=2.0, buy_price=50_000_000.0)

    trade = await _record_sell_as_fifo(
        lot=lot,
        symbol=SYMBOL,
        quantity=2.0,
        price=50_000_000.0,
        amount_irt=100_000_000.0,
        fee_pct=1.0,
    )

    assert lot.quantity == 0.0
    assert lot.buy_amount_irt == 0.0
    assert lot.deleted_at is not None
    assert trade.fee_irt == pytest.approx(1_000_000.0)
    assert trade.pnl_irt == pytest.approx(-1_000_000.0)


async def test_oversell_raises_insufficient_holding_error() -> None:
    lot = _lot(1, quantity=2.0, buy_price=50_000_000.0)

    with pytest.raises(InsufficientHoldingError, match="not enough quantity"):
        await _record_sell_as_fifo(
            lot=lot,
            symbol=SYMBOL,
            quantity=3.0,
            price=60_000_000.0,
            amount_irt=180_000_000.0,
        )


async def test_requires_lot_or_lots() -> None:
    with pytest.raises(ValueError, match="either lot or lots"):
        await _record_sell_as_fifo(
            symbol=SYMBOL,
            quantity=1.0,
            price=1.0,
            amount_irt=1.0,
        )
