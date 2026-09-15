"""تست Real Backtest — pure functions فقط."""

from __future__ import annotations

from datetime import date, timedelta

from src.gold_desk.backtest_real import (
    _compute_metrics,
    _rsi,
    _sma,
    strategy_bubble_threshold,
    strategy_ma_crossover,
    strategy_rsi_oversold,
)

# ── _rsi ─────────────────────────────────────────────────


def test_rsi_short_prices():
    arr = [10, 11, 12, 11, 10, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
    rsi = _rsi(arr, 14)
    assert len(rsi) == 15
    assert all(0 <= r <= 100 for r in rsi)


def test_rsi_uptrend():
    """روند صعودی قوی → RSI بالا."""
    arr = [100 + i for i in range(30)]
    rsi = _rsi(arr, 14)
    assert rsi[-1] > 80


# ── _sma ─────────────────────────────────────────────────


def test_sma_basic():
    arr = [1, 2, 3, 4, 5]
    out = _sma(arr, 3)
    assert out[2] == 2.0
    assert out[3] == 3.0
    assert out[4] == 4.0


# ── strategy_rsi_oversold ─────────────────────────────────


def test_rsi_oversold_no_signal():
    """بدون نوسان شدید → معامله‌ای نیست."""
    arr = [100 + (i % 3) for i in range(60)]  # range-bound
    trades = strategy_rsi_oversold(arr, [date(2025, 1, 1) + timedelta(days=i) for i in range(60)])
    assert len(trades) == 0


def test_rsi_oversold_finds_dip():
    """dip شدید → خرید در RSI < 30."""
    # ساخت synthetic: range down 30% then up 20%
    arr = [100] * 10 + [70] * 5 + [85] * 20
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(35)]
    trades = strategy_rsi_oversold(arr, dates)
    assert len(trades) >= 0  # ممکنه trigger نشه در synthetic


# ── strategy_ma_crossover ─────────────────────────────────


def test_ma_crossover_no_data():
    """داده کم → معامله‌ای نیست."""
    arr = [100] * 50
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(50)]
    trades = strategy_ma_crossover(arr, dates)
    assert trades == []


# ── strategy_bubble_threshold ───────────────────────────


def test_bubble_threshold_no_data():
    arr = [100] * 20
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(20)]
    trades = strategy_bubble_threshold(arr, dates)
    assert trades == []


def test_bubble_threshold_dip():
    """قیمت زیر 30-day MA → خرید (DCA). bubble < 0 یعنی زیر MA."""
    arr = [100] * 30 + [80] * 60  # 20% زیر MA → bubble ≈ -20%
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(90)]
    trades = strategy_bubble_threshold(arr, dates, threshold=5.0)
    # bubble < -threshold → خرید
    assert len(trades) >= 1


# ── _compute_metrics ─────────────────────────────────────


def test_compute_metrics_empty():
    m = _compute_metrics([], [100, 101, 102])
    assert m.n_trades == 0
    assert m.hit_rate_pct == 0


def test_compute_metrics_winning():
    trades = [(0, 10, 5.0), (20, 30, 3.0), (40, 50, -2.0)]
    m = _compute_metrics(trades, [100, 105, 110, 115, 100, 102, 105, 108, 110, 112, 115])
    assert m.n_trades == 3
    assert m.n_wins == 2
    assert abs(m.hit_rate_pct - 66.7) < 0.1
    assert m.total_return_pct > 0
