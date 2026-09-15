"""تست Backtest Runner — pure functions."""

from __future__ import annotations

from datetime import date, timedelta

from src.gold_desk.backtest_runner import (
    BacktestTrade,
    _compute_metrics,
    _simulate_dca,
)


# Fixtures
def make_closes(n: int = 90, trend: float = 0.001) -> list[tuple[date, float]]:
    """n روز close با trend جزئی."""
    base = 50_000_000
    start = date(2025, 1, 1)
    return [(start + timedelta(days=i), base * (1 + trend) ** i) for i in range(n)]


def test_simulate_dca_basic():
    closes = make_closes(90, trend=0.001)  # صعودی ملایم
    trades = _simulate_dca(closes, [0.3, 0.4, 0.3], bubble_trigger=5.0)
    assert len(trades) >= 1
    # پله اول باید خریده باشد
    assert trades[0].tranche == 1
    assert trades[0].units > 0


def test_simulate_dca_high_bubble():
    """اگر bubble بالا → پله اول skip."""
    closes = make_closes(90, trend=0.005)  # صعودی قوی = bubble بالا
    trades = _simulate_dca(closes, [0.3, 0.4, 0.3], bubble_trigger=2.0)
    # ممکنه پله 1 trigger نشود ولی پله 3 حتماً
    assert len(trades) >= 1


def test_simulate_dca_insufficient_data():
    closes = make_closes(5, trend=0.001)
    trades = _simulate_dca(closes, [0.3, 0.4, 0.3], bubble_trigger=5.0)
    assert len(trades) == 0


def test_compute_metrics_basic():
    closes = make_closes(90, trend=0.002)
    trades = _simulate_dca(closes, [0.3, 0.4, 0.3], bubble_trigger=5.0)
    metrics = _compute_metrics(closes, trades, 100_000_000)
    assert metrics.n_trades > 0
    assert metrics.period_start == closes[0][0]
    assert metrics.period_end == closes[-1][0]


def test_metrics_empty_data():
    m = _compute_metrics([], [], 100_000_000)
    assert m.n_trades == 0
    assert m.warning == "insufficient data"


def test_metrics_warning_small_sample():
    closes = make_closes(90, trend=0.001)
    fake_trade = BacktestTrade(
        date=closes[0][0], tranche=1, price=50_000_000, amount_irt=30_000_000, units=0.6, trigger_met=True
    )
    m = _compute_metrics(closes, [fake_trade], 100_000_000)
    assert m.warning is not None
    assert "too small" in m.warning


def test_metrics_buy_hold_calculated():
    closes = make_closes(90, trend=0.002)
    trades = _simulate_dca(closes, [0.3, 0.4, 0.3], bubble_trigger=5.0)
    m = _compute_metrics(closes, trades, 100_000_000)
    # buy-hold return باید مثبت باشد (صعودی)
    assert m.buy_hold_return_pct > 0


def test_metrics_alpha_calculation():
    closes = make_closes(90, trend=0.001)
    trades = _simulate_dca(closes, [0.3, 0.4, 0.3], bubble_trigger=5.0)
    m = _compute_metrics(closes, trades, 100_000_000)
    # alpha = total - buy_hold
    assert abs(m.alpha_pct - (m.total_return_pct - m.buy_hold_return_pct)) < 0.01
