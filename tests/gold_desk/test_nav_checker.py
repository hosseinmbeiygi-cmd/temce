"""تست NAV Checker — انتخاب NAV، BPR، تازگی داده و خطاها.

این ماژول پیش‌تر هیچ تست اختصاصی در ``tests/gold_desk`` نداشت (بخش ۸ گزارش ۰۱).
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

from src.gold_desk.dates import jalali_days_ago
from src.gold_desk.nav_checker import (
    _fund_market_data,
    _pick_nav,
    get_all_funds_status,
)


class _Res:
    def __init__(self, row):
        self._row = row

    def scalars(self):
        return self

    def first(self):
        return self._row

    def all(self):
        return self._row or []


class _Session:
    """جایگزین AsyncSession برای تست‌های pure."""

    def __init__(self, row=None, rows=None, exc=None):
        self._row = row
        self._rows = rows
        self._exc = exc
        self.calls = 0

    async def execute(self, _stmt):
        self.calls += 1
        if self._exc:
            raise self._exc
        if self._rows is not None:
            return _Res(self._rows)
        return _Res(self._row)


def _real_legal(date: str, buy: float | None, sell: float | None):
    return SimpleNamespace(date=date, buy_real_value=buy, sell_real_value=sell)


def _non_padded(jalali: str) -> str:
    """همان تاریخ بدون صفر پیشوند (مثل داده‌ای که بعضی منابع می‌دهند)."""
    year, month, day = jalali.split("-")
    return f"{int(year)}-{int(month)}-{int(day)}"


# ── E-M4: BPR نامعتبر نباید صفر شود ─────────────────────────────


def test_bpr_none_when_no_sell_value():
    """sell_real_value صفر ⇒ BPR تعریف‌ناپذیر، نه ۰ (که وزن ۱۸ را صفر امتیاز می‌کند)."""
    row = _real_legal(jalali_days_ago(1), 1_000_000.0, 0.0)
    data = asyncio.run(_fund_market_data(_Session(row), "عیار"))
    assert data is not None
    assert data["bpr"] is None
    # جریان خالص هنوز عددی و قابل استفاده است
    assert data["net_inflow"] == 1_000_000


def test_bpr_computed_when_both_sides_exist():
    row = _real_legal(jalali_days_ago(1), 3_000_000.0, 1_000_000.0)
    data = asyncio.run(_fund_market_data(_Session(row), "عیار"))
    assert data is not None
    assert data["bpr"] == 3.0


# ── E-M5: مقایسهٔ تاریخ شمسی با parse واقعی ─────────────────────


def test_stale_data_detected_for_non_padded_jalali_date():
    """تاریخ ۳۰ روز قبل ولی بدون صفر پیشوند: مقایسهٔ رشته‌ای آن را «تازه» می‌دید."""
    stale = _non_padded(jalali_days_ago(30))
    row = _real_legal(stale, 1_000_000.0, 500_000.0)
    assert asyncio.run(_fund_market_data(_Session(row), "عیار")) is None


def test_fresh_data_accepted():
    row = _real_legal(jalali_days_ago(1), 1_000_000.0, 500_000.0)
    assert asyncio.run(_fund_market_data(_Session(row), "عیار")) is not None


def test_unparsable_date_rejected_with_warning(caplog):
    row = _real_legal("not-a-date", 1_000_000.0, 500_000.0)
    with caplog.at_level(logging.WARNING, logger="src.gold_desk.nav_checker"):
        assert asyncio.run(_fund_market_data(_Session(row), "عیار")) is None
    assert any("unparsable" in r.message.lower() or "date" in r.message.lower() for r in caplog.records)


# ── E-L7: استثنا نباید بی‌صدا خورده شود ──────────────────────────


def test_market_data_exception_is_logged(caplog):
    session = _Session(exc=RuntimeError("boom"))
    with caplog.at_level(logging.WARNING, logger="src.gold_desk.nav_checker"):
        assert asyncio.run(_fund_market_data(session, "عیار")) is None
    assert caplog.records, "خطا باید لاگ شود، نه سکوت"
    assert "عیار" in caplog.text


# ── E-M3: انتخاب صریح nav_issue ─────────────────────────────────


def test_pick_nav_prefers_nav_issue():
    assert _pick_nav((1_000.0, 1_300.0)) == 1_000.0


def test_pick_nav_reports_issue_redemption_divergence(caplog):
    with caplog.at_level(logging.WARNING, logger="src.gold_desk.nav_checker"):
        assert _pick_nav((1_000.0, 1_300.0)) == 1_000.0
    assert any("nav" in r.message.lower() for r in caplog.records)


def test_pick_nav_falls_back_to_redemption():
    assert _pick_nav((None, 1_300.0)) == 1_300.0
    assert _pick_nav((0.0, 1_300.0)) == 1_300.0
    assert _pick_nav((None, None)) is None


# ── E-L8: یک کوئری batch به‌جای N+1 ─────────────────────────────


def test_all_funds_status_uses_batch_queries():
    """با ۳ نماد نباید ۳ برابر کوئری زده شود."""
    session = _Session(rows=[])
    asyncio.run(get_all_funds_status(session, ["عیار", "طلا", "زر"], market_prices={}))
    assert session.calls <= 4, f"{session.calls} queries for 3 symbols"
