"""تست Signal Engine — ترتیب سری، اندیکاتورها و حالت‌های حدی.

این ماژول پیش‌تر هیچ تستی در ``tests/gold_desk`` نداشت (بخش ۸ گزارش ۰۱).
"""

from __future__ import annotations

import asyncio

from src.gold_desk.signal_engine import (
    _fetch_gold_coin_closes,
    calc_bollinger,
    calc_ema,
    calc_ema_bubble,
    calc_macd,
    calc_rsi,
    calc_sma,
    fetch_closes,
)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeSession:
    """جایگزین AsyncSession — ردیف‌ها را به همان ترتیبی که DB می‌دهد برمی‌گرداند."""

    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _stmt):
        return _FakeResult(self._rows)


# ── E-H1: ترتیب سری ────────────────────────────────────────────


def test_fetch_returns_newest_window_in_chronological_order():
    """DB نزولی می‌دهد (جدیدترین اول)؛ خروجی باید صعودی و شامل جدیدترین‌ها باشد."""
    # 40 ردیف، جدیدترین اول: 40, 39, ..., 1
    rows = [(float(i),) for i in range(40, 0, -1)]
    session = _FakeSession(rows)

    closes = asyncio.run(_fetch_gold_coin_closes(session, "IR_COIN_EMAMI", days=30))

    assert len(closes) == 30
    # جدیدترین مقدار آخر لیست است
    assert closes[-1] == 40.0
    assert closes[0] == 11.0
    # صعودی است (قدیم → جدید)
    assert closes == sorted(closes)
    # ردیف‌های جدیدتر نباید حذف شوند
    assert 39.0 in closes and 40.0 in closes


def test_fetch_closes_keeps_row_order_through_fallback():
    rows = [(float(i),) for i in range(40, 0, -1)]
    session = _FakeSession(rows)
    closes = asyncio.run(fetch_closes(session, "IR_COIN_EMAMI", days=30))
    assert closes[-1] == 40.0


def test_rsi_uses_latest_value_not_stale_window():
    """RSI روی سری ۴۰ تایی باید آخرین مقدار را ببیند، نه ۱۰ روز قبل را."""
    # ۳۰ روز ثابت + ۱۰ روز صعودی: RSI باید به اشباع خرید نزدیک شود
    closes = [100.0] * 30 + [100.0 + i for i in range(1, 11)]
    rsi = calc_rsi(closes, 14)
    assert rsi is not None
    assert rsi > 90.0


def test_ema_uses_latest_value():
    closes = [float(i) for i in range(1, 41)]
    ema = calc_ema(closes, 14)
    assert ema is not None
    # EMA باید نزدیک انتهای سری باشد، نه نزدیک میانه/ابتدا
    assert ema > 25.0


# ── E-L5: سری بدون تغییر ──────────────────────────────────────


def test_rsi_all_gains_is_100():
    rsi = calc_rsi([100.0 + i for i in range(30)], 14)
    assert rsi == 100.0


# ── اندیکاتورهای پایه ──────────────────────────────────────────


def test_rsi_insufficient_data():
    assert calc_rsi([100.0] * 5, 14) is None


def test_sma_and_bollinger():
    closes = [float(i) for i in range(1, 31)]
    assert calc_sma(closes, 20) == 20.5
    bb = calc_bollinger(closes, 20)
    assert bb is not None
    assert bb["lower"] < bb["middle"] < bb["upper"]
    assert bb["width_pct"] > 0


def test_macd_insufficient_data():
    assert calc_macd([100.0] * 30) is None


def test_macd_bullish_on_uptrend():
    closes = [100.0 + i for i in range(60)]
    macd = calc_macd(closes)
    assert macd is not None
    assert macd["bullish"] is True


def test_ema_bubble_positive_on_spike():
    closes = [100.0] * 25 + [130.0]
    bubble = calc_ema_bubble(closes, 20)
    assert bubble is not None
    assert bubble > 0
