"""تست قرارداد FIFO در سرویس پورتفایل (per-symbol).

C9: فروش از نمادی بدون لات باز، استثنای صریح (explicit error) مفروض شود تا
    بای تحقق‌یافته به‌جای نادیده‌گیری و بای صفر، رصد و از اعداد مالیاتی درست
    بماند؛ همچنین FIFO بین نمادها مرز بگیرد.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.gold_desk.portfolio import fifo_realized

D = datetime(2026, 1, 1)


class _T:
    def __init__(self, action: str, qty: float, price: float, symbol: str, when: datetime = D):
        self.action = action
        self.quantity = qty
        self.price = price
        self.traded_at = when
        self.symbol = symbol


def _buy(qty, price, symbol) -> _T:
    return _T("buy", qty, price, symbol)


def _sell(qty, price, symbol) -> _T:
    return _T("sell", qty, price, symbol)


def test_fifo_per_symbol_does_not_mix_symbols():
    """فروشِ نماد A لات‌های نماد B را از بین نبرده؛ هردو نماد باقی بمانند."""
    trades = [
        _buy(10, 100.0, "A"),
        _buy(5, 200.0, "B"),
        _sell(3, 150.0, "A"),
    ]
    out = fifo_realized(trades)
    # فقط ۳ لات A deliberate است؛ سود (۱۵۰-۱۰۰)*۳ = ۱۵۰
    assert out["realized_pnl_irt"] == pytest.approx(150.0)
    # B لات ۵@۲۰۰ کاملاً باقی بماند
    assert [o["quantity"] for o in out["open_lots"]] == [pytest.approx(7.0), pytest.approx(5.0)]
    assert out["sold_quantity"] == pytest.approx(3.0)
    assert out["open_quantity"] == pytest.approx(12.0)
    assert out["open_cost_basis_irt"] == pytest.approx(700.0 + 1000.0)


def test_fifo_sell_without_lots_raises_explicit_error():
    """فروش از نمادی بدون لات باید خطا بدهد، نه بای را صفر بگذارد."""
    trades = [
        _buy(5, 100.0, "A"),
        _sell(3, 150.0, "B"),  # B هرگز خریداری نشده
    ]
    with pytest.raises(ValueError, match="FifoError"):
        fifo_realized(trades)


def test_fifo_regressions_existing_case():
    """مثالی که تست رگرسیون قبلی انتظار دارد (سطح واحد)."""
    trades = [
        _T("buy", 10, 100.0, "A", D),
        _T("buy", 5, 120.0, "A", D),
        _T("sell", 12, 150.0, "A", D),
    ]
    out = fifo_realized(trades)
    assert out["realized_pnl_irt"] == pytest.approx(560.0)
    assert out["sold_quantity"] == pytest.approx(12.0)
    assert out["open_quantity"] == pytest.approx(3.0)
    assert out["open_cost_basis_irt"] == pytest.approx(360.0)
    assert [o["quantity"] for o in out["open_lots"]] == [pytest.approx(3.0)]
