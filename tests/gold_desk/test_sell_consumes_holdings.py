"""فروش باید موجودی لات‌ها را کم کند و P&L را FIFO حساب کند (W4-01/W4-08/W4-09).

قبلاً ``record_trade`` فقط ردیف trade را می‌نوشت و ``quantity`` دارایی دست‌نخورده
می‌ماند؛ بنابراین پورتفوی پس از فروش همان تعداد قبل را نشان می‌داد.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

T0 = datetime(2026, 1, 1)
T1 = datetime(2026, 2, 1)


class FakeSession:
    """حداقل session لازم برای مسیر فروش/خرید."""

    def __init__(self, holdings: list[SimpleNamespace] | None = None) -> None:
        self.by_id = {h.id: h for h in (holdings or [])}
        self.added: list[object] = []
        self.commits = 0

    async def get(self, _model, pk):
        return self.by_id.get(pk)

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _obj) -> None:
        return None

    async def execute(self, *args, **kwargs):
        # FakeSession ثبت‌نشده; این تست از مکانیسم FIFO تابع کمکی
        # _record_sell_as_fifo استفاده می‌کند که مستقیم روی لات‌ها کار می‌کند.
        raise NotImplementedError("FakeSession uses _record_sell_as_fifo path")


def _lot(holding_id: int, quantity: float, buy_price: float, bought_at=T0):
    return SimpleNamespace(
        id=holding_id,
        symbol="IR_GOLD_18K",
        quantity=quantity,
        buy_price=buy_price,
        buy_amount_irt=quantity * buy_price,
        bought_at=bought_at,
        deleted_at=None,
        user_id=None,
    )


async def test_partial_sell_decrements_quantity_and_cost_basis() -> None:
    # TODO(owner): finish the assertions for W4-01/W4-08/W4-09. ``_lot`` and
    # ``FakeSession`` above are kept ready for that work; the test is skipped
    # so an unfinished body cannot masquerade as coverage.
    pytest.skip("WIP: assertions for the partial-sell path are not written yet")
