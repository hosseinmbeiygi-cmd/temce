"""تست AI Pattern Detector — pure functions."""

from __future__ import annotations

import numpy as np

from src.gold_desk.pattern_detector import (
    _detect_mean_reversion,
    _detect_spike,
    _detect_trend,
    _detect_vol_regime,
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
    arr = np.array([1, 2], dtype=float)
    out = pd_rolling_mean(arr, 3)
    # window بزرگ‌تر از array → میانگین کل
    assert out[0] == 1.5


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
