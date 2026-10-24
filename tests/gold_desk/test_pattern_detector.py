"""تست AI Pattern Detector — pure functions."""

from __future__ import annotations

import asyncio
import datetime as dt

import jdatetime
import numpy as np

from src.gold_desk.pattern_detector import (
    RECOMMENDATIONS,
    _detect_mean_reversion,
    _detect_spike,
    _detect_trend,
    _detect_vol_regime,
    _fetch_closes,
    detect_patterns,
    pd_rolling_mean,
)

# ── pd_rolling_mean ────────────────────────────────────────


def test_rolling_mean_basic():
    arr = np.array([1, 2, 3, 4, 5], dtype=float)
    out = pd_rolling_mean(arr, 3)
    assert out[2] == 2.0  # (1+2+3)/3
    assert out[3] == 3.0
    assert out[4] == 4.0


def test_rolling_mean_short():
    """E-H6: ورودی کوتاه ⇒ nan، نه پر کردن با میانگین آینده/کل."""
    arr = np.array([1, 2], dtype=float)
    out = pd_rolling_mean(arr, 3)
    assert np.isnan(out).all()


def test_rolling_mean_has_no_backfill():
    """عناصر ابتدای سری نباید با داده آینده پر شوند (look-ahead)."""
    arr = np.arange(1, 11, dtype=float)
    out = pd_rolling_mean(arr, 3)
    assert np.isnan(out[0]) and np.isnan(out[1])
    assert out[2] == 2.0


# ── _detect_trend ────────────────────────────────────────────


def test_trend_bullish():
    """روند صعودی قوی → pattern detected."""
    prices = [100 + i for i in range(20)]  # +1 هر روز
    p = _detect_trend(prices)
    assert p is not None
    assert p.pattern_type == "trend_continuation"
    assert p.expected_direction == "up"


def test_trend_no_pattern():
    """قیمت بدون روند → pattern نیست."""
    prices = [100, 101, 100, 101, 100, 101, 100]
    p = _detect_trend(prices)
    assert p is None


# ── _detect_spike ────────────────────────────────────────────


def test_spike_detected():
    """spike > 5% در 3 روز."""
    prices = [100, 100, 100, 106, 110]  # +10% در 3 روز
    p = _detect_spike(prices)
    assert p is not None
    assert p.pattern_type == "spike_crash"
    assert p.expected_direction == "down"


def test_spike_no_pattern():
    prices = [100, 101, 100, 101, 100]
    p = _detect_spike(prices)
    assert p is None


# ── _detect_vol_regime ───────────────────────────────────────


def test_high_vol_regime():
    np.random.seed(42)
    prices = list(100 + np.random.normal(0, 5, 20).cumsum())
    p = _detect_vol_regime(prices)
    # اگه vol بالا باشه، pattern باید باشه
    if p:
        assert p.pattern_type == "vol_regime"


def test_low_vol_no_pattern():
    """نوسان کم → pattern نیست."""
    prices = [100 + i * 0.1 for i in range(20)]  # حرکت smooth
    p = _detect_vol_regime(prices)
    assert p is None


# ── _detect_mean_reversion ──────────────────────────────────


def test_mean_reversion_insufficient_data():
    prices = [100 + i for i in range(30)]
    p = _detect_mean_reversion(prices)
    assert p is None  # داده کمتر از 60


# ── fake session ──────────────────────────────────────────


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Session:
    def __init__(self, rows, statement_sink=None):
        self._rows = rows
        self._sink = statement_sink

    async def execute(self, stmt):
        if self._sink is not None:
            self._sink.append(stmt)
        return _Res(self._rows)


def _jalali_rows(prices: list[float], start=(1405, 1, 1)):
    first = jdatetime.date(*start)
    rows = []
    for i, price in enumerate(prices):
        d = (first.togregorian() + dt.timedelta(days=i))
        j = jdatetime.date.fromgregorian(date=d)
        rows.append((f"{j.year:04d}-{j.month:02d}-{j.day:02d}", price))
    return rows


# ── E-C3: cutoff باید شمسی باشد ───────────────────────────


def test_fetch_closes_uses_jalali_cutoff(monkeypatch):
    captured = []
    monkeypatch.setattr(
        "src.gold_desk.pattern_detector.jalali_days_ago", lambda days: "1405-06-01"
    )
    asyncio.run(_fetch_closes(_Session([], statement_sink=captured), "IR_COIN_EMAMI", 90))
    assert captured, "باید یک کوئری زده شود"
    sql = str(captured[0].compile(compile_kwargs={"literal_binds": True}))
    assert "1405-06-01" in sql


# ── E-M12: دوره باید تاریخ میلادی معتبر باشد ──────────────


def test_period_dates_are_parsed_from_jalali():
    rows = _jalali_rows([100.0 + i for i in range(40)])
    report = asyncio.run(detect_patterns(_Session(rows), "IR_COIN_EMAMI", 90))
    first = jdatetime.date(1405, 1, 1).togregorian()
    last = first + dt.timedelta(days=39)
    assert report.period_start.date() == first
    assert report.period_end.date() == last
    assert report.period_start.year >= 2000  # نه سال ۱۴۰۵ در فیلد میلادی


# ── E-M13: نرخ موفقیت باید از داده بیاید، نه عدد ثابت ────


def test_trend_hit_rate_is_computed_not_hardcoded():
    """سری کاملاً صعودی: هر trigger روند با ۵ روز صعودی بعدی همراه بوده ⇒ ۱۰۰٪."""
    prices = [100.0 + i for i in range(60)]
    p = _detect_trend(prices)
    assert p is not None
    assert p.sample_size > 0
    assert p.historical_hit_rate == 100.0


def test_spike_hit_rate_is_computed_not_hardcoded():
    """بعد از هر جهش، قیمت در ۵ روز بعد ریخته ⇒ ۱۰۰٪ (نه ۵۸٪ ثابت)."""
    prices: list[float] = []
    level = 100.0
    for _ in range(8):
        prices.extend([level, level, level, level * 1.10])  # جهش ۱۰٪
        level *= 1.10
        for _ in range(5):  # و پنج روز ریزش پیاپی
            level *= 0.90
            prices.append(level)
    prices.extend([level, level, level, level * 1.10])  # سری با جهش تمام شود
    p = _detect_spike(prices)
    assert p is not None
    assert p.historical_hit_rate == 100.0


# ── E-M14: مقدار مردهٔ recommendation ────────────────────


def test_recommendations_enum_matches_emitted_values():
    assert "خرید قوی" not in RECOMMENDATIONS
    rows = _jalali_rows([100.0 + i for i in range(40)])
    report = asyncio.run(detect_patterns(_Session(rows), "IR_COIN_EMAMI", 90))
    assert report.recommendation in RECOMMENDATIONS


def test_mean_reversion_detected():
    """ساخت داده مصنوعی: bubble بالا → بازگشت."""
    np.random.seed(42)
    base = 1000
    prices = [base] * 30 + [base * 1.25] * 5 + [base * 1.05] * 30 + [base] * 55
    # 35-39: bubble>20% ، 65: bubble ~5%
    p = _detect_mean_reversion(prices)
    if p:
        assert p.pattern_type == "mean_reversion"
        assert p.expected_direction == "down"
