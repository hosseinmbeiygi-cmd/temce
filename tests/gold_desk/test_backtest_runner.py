"""تست Backtest Runner — pure functions."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

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
    """اگر bubble بالا باشد پلهٔ اول اجرا نمی‌شود.

    E-H3: پیش‌تر پلهٔ ۲ در نبود پلهٔ ۱ بی‌قید و شرط می‌خرید و تست همین را تأیید
    می‌کرد. اکنون زنجیره واقعی است: بدون پلهٔ ۱ هیچ پله‌ای اجرا نمی‌شود.
    """
    closes = make_closes(90, trend=0.005)  # صعودی قوی = bubble بالا
    trades = _simulate_dca(closes, [0.3, 0.4, 0.3], bubble_trigger=2.0)
    assert trades == []


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


# ── E-C1: مقیاس بازده باید با سرمایه واقعی هم‌واحد باشد ─────


def test_total_return_has_realistic_magnitude():
    """تست اجباری گزارش ۰۱: در بازار صعودی بازده نمی‌تواند -۱۰۰٪ باشد."""
    closes = make_closes(90, trend=0.002)
    trades = _simulate_dca(closes, [0.3, 0.4, 0.3], bubble_trigger=5.0, initial_capital=100_000_000)
    m = _compute_metrics(closes, trades, 100_000_000)
    assert -50 < m.total_return_pct < 200
    assert -50 < m.alpha_pct < 200
    # ارزش نهایی باید هم‌مرتبه با سرمایه اولیه باشد، نه ~۰.۵
    assert 0.5 * m.initial_capital < m.final_value < 2.0 * m.initial_capital


def test_units_use_real_capital():
    closes = make_closes(90, trend=0.002)
    trades = _simulate_dca(closes, [0.3, 0.4, 0.3], bubble_trigger=5.0, initial_capital=100_000_000)
    assert trades
    first = trades[0]
    assert first.amount_irt == pytest.approx(0.30 * 100_000_000)
    assert first.units * first.price == pytest.approx(first.amount_irt * (1 - 0.0), rel=1e-9)


def test_fee_is_deducted_from_units():
    closes = make_closes(90, trend=0.002)
    trades = _simulate_dca(
        closes, [0.3, 0.4, 0.3], bubble_trigger=5.0, initial_capital=100_000_000, fee_pct=0.015
    )
    first = trades[0]
    assert first.units * first.price == pytest.approx(first.amount_irt * (1 - 0.015))
    assert first.fee_irt == pytest.approx(first.amount_irt * 0.015)


# ── E-H2: drawdown از NAV روزانه ────────────────────────────────


def test_max_drawdown_positive_on_falling_series():
    """سری که اوج می‌گیرد و ۳۰٪ می‌ریزد باید drawdown مثبت نشان دهد."""
    closes = make_closes(60, trend=0.01)
    falling = [(d, p * 0.70) for d, p in closes[40:]]
    series = closes[:40] + falling
    trades = _simulate_dca(series, [1.0, 0.0, 0.0], bubble_trigger=99.0, initial_capital=100_000_000)
    m = _compute_metrics(series, trades, 100_000_000)
    assert m.max_drawdown_pct > 0
    assert m.max_drawdown_pct < 100


def test_sharpe_uses_strategy_nav():
    """Sharpe روی NAV استراتژی است، نه سری دارایی پایه."""
    closes = make_closes(90, trend=0.002)
    trades = _simulate_dca(closes, [1.0, 0.0, 0.0], bubble_trigger=99.0, initial_capital=100_000_000)
    m = _compute_metrics(closes, trades, 100_000_000)
    # با سرمایهٔ نقد نشسته (بدون معامله) نوسان NAV صفر است
    no_trades = _compute_metrics(closes, [], 100_000_000)
    assert no_trades.sharpe_ratio == 0
    assert isinstance(m.sharpe_ratio, float)


# ── E-H3: پله‌ها رویدادمحور و زنجیره‌ای ────────────────────────


def test_tranches_are_chained_and_event_driven():
    """در روند صعودی بدون اصلاح، فقط پلهٔ اول اجرا می‌شود (نه پله ۳ بی‌قید)."""
    closes = make_closes(90, trend=0.002)
    trades = _simulate_dca(closes, [0.3, 0.4, 0.3], bubble_trigger=5.0, initial_capital=100_000_000)
    assert [t.tranche for t in trades] == [1]


def test_pullback_tranche_runs_after_pullback():
    """بعد از اصلاح ۳-۵٪، پلهٔ دوم اجرا می‌شود."""
    closes = make_closes(40, trend=0.001)
    last = closes[-1][1]
    # اصلاح ۴٪ در سه روز
    pull = [(closes[-1][0] + timedelta(days=i + 1), last * 0.96) for i in range(3)]
    series = closes + pull
    trades = _simulate_dca(series, [0.5, 0.5, 0.0], bubble_trigger=99.0, initial_capital=100_000_000)
    assert [t.tranche for t in trades] == [1, 2]


# ── نمونهٔ خارج از نمونه ─────────────────────────────────────


def test_out_of_sample_metrics_present():
    closes = make_closes(90, trend=0.002)
    trades = _simulate_dca(closes, [0.3, 0.4, 0.3], bubble_trigger=5.0, initial_capital=100_000_000)
    m = _compute_metrics(closes, trades, 100_000_000)
    assert m.oos_total_return_pct is not None
    assert m.oos_buy_hold_return_pct is not None
    assert m.warning is not None and "out-of-sample" in m.warning
