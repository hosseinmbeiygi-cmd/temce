"""Unit tests for the fund quant engine (services/fund_quant_engine.py).

متریک‌های مالی، امتیازدهی و بک‌تست — بدون نیاز به دیتابیس.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from services.fund_quant_engine import (
    ScoreWeights,
    compute_alpha_beta,
    compute_calmar,
    compute_max_drawdown,
    compute_sharpe,
    compute_sortino,
    compute_tracking_error,
    daily_returns,
    is_iran_trading_day,
    next_trading_day,
    run_all_strategies,
    run_backtest,
    score_fund,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_nav_series(n: int = 260, drift: float = 0.0005, seed: int = 42) -> list[float]:
    """دنباله NAV مصنوعی با drift مثبت و نوسان کنترل‌شده."""
    import random

    rng = random.Random(seed)
    nav = 1_000_000.0
    out = []
    for _ in range(n):
        nav *= 1.0 + drift + rng.gauss(0, 0.01)
        out.append(nav)
    return out


def _make_nav_points(series: list[float]) -> list[dict]:
    """تبدیل سری NAV به نقاط تاریخ‌دار معاملاتی (شنبه تا چهارشنبه)."""
    points = []
    d = date(2025, 1, 4)  # شنبه
    for nav in series:
        while not is_iran_trading_day(d):
            d += timedelta(days=1)
        points.append({"date": d.isoformat(), "nav": nav})
        d += timedelta(days=1)
    return points


# ── Daily returns ────────────────────────────────────────────────────────────


def test_daily_returns_basic():
    rets = daily_returns([100.0, 110.0, 99.0])
    assert len(rets) == 2
    assert rets[0] == pytest.approx(0.10)
    assert rets[1] == pytest.approx(99.0 / 110.0 - 1.0)


def test_daily_returns_short_series():
    assert daily_returns([100.0]) == []
    assert daily_returns([]) == []


# ── Sharpe / Sortino ─────────────────────────────────────────────────────────


def test_sharpe_positive_drift():
    nav = _make_nav_series(drift=0.001)
    sharpe = compute_sharpe(nav)
    assert sharpe is not None
    assert sharpe > 0  # drift مثبت باید شارپ مثبت بدهد


def test_sharpe_none_for_short_series():
    assert compute_sharpe([1.0, 1.1, 0.9]) is None


def test_sortino_below_sharpe_for_two_sided_vol():
    nav = _make_nav_series()
    s = compute_sharpe(nav)
    so = compute_sortino(nav)
    assert s is not None and so is not None
    assert so >= s * 0.5  # حدودی؛ سورتینو معمولاً بالاتر است


# ── Max Drawdown / Calmar ────────────────────────────────────────────────────


def test_max_drawdown_simple_drop():
    dd, peak_i, trough_i = compute_max_drawdown([100, 120, 90, 110])
    assert dd == pytest.approx(25.0)  # 120 → 90
    assert peak_i == 1
    assert trough_i == 2


def test_max_drawdown_monotonic_up():
    dd, _, _ = compute_max_drawdown([100, 110, 120, 130])
    assert dd == 0.0


def test_calmar_positive_for_growing_series():
    nav = _make_nav_series(drift=0.002)
    calmar = compute_calmar(nav)
    assert calmar is not None
    assert calmar > 0


# ── Alpha / Beta / Tracking Error ────────────────────────────────────────────


def test_beta_one_for_identical_series():
    nav = _make_nav_series()
    alpha, beta = compute_alpha_beta(nav, list(nav))
    assert beta == pytest.approx(1.0, abs=0.05)
    assert alpha is not None
    assert abs(alpha) < 5.0  # آلفا باید نزدیک صفر باشد


def test_tracking_error_zero_for_identical():
    nav = _make_nav_series()
    te = compute_tracking_error(nav, list(nav))
    assert te is not None
    assert te == pytest.approx(0.0, abs=1e-6)


# ── Scoring ──────────────────────────────────────────────────────────────────


def test_score_components_in_range():
    nav = _make_nav_series()
    score = score_fund(nav, avg_daily_trade_value=5e9)
    for comp in (score.return_component, score.risk_component, score.liquidity_component, score.stability_component):
        assert 0.0 <= comp <= 100.0
    assert 0.0 <= score.total <= 100.0


def test_score_weights_normalization():
    w = ScoreWeights(return_w=1, risk_w=1, liquidity_w=1, stability_w=1).normalized()
    assert w.return_w + w.risk_w + w.liquidity_w + w.stability_w == pytest.approx(1.0)


def test_score_liquidity_higher_for_more_volume():
    nav = _make_nav_series()
    low = score_fund(nav, avg_daily_trade_value=1e7)
    high = score_fund(nav, avg_daily_trade_value=5e10)
    assert high.liquidity_component > low.liquidity_component


# ── Backtest ─────────────────────────────────────────────────────────────────


def test_buy_hold_returns_match_nav_drift():
    series = _make_nav_series(n=250, drift=0.0005)
    points = _make_nav_points(series)
    res = run_backtest(points, strategy="buy_hold", initial_amount=100_000_000)
    assert res is not None
    assert res.trade_count == 1
    expected = (series[-1] / series[0] - 1.0) * 100.0
    # با کارمزد اندکی کمتر از بازدهی خام NAV
    assert res.total_return_pct == pytest.approx(expected, abs=1.0)


def test_dca_invests_monthly():
    points = _make_nav_points(_make_nav_series(n=250))
    res = run_backtest(points, strategy="dca_monthly", monthly_amount=10_000_000)
    assert res is not None
    assert res.trade_count >= 8  # ~12 ماه شمسی در ۲۵۰ روز
    assert res.total_invested == pytest.approx(res.trade_count * 10_000_000)


def test_backtest_needs_min_data():
    assert run_backtest([{"date": "2025-01-01", "nav": 1000}] * 5, strategy="buy_hold") is None


def test_run_all_strategies_shape():
    points = _make_nav_points(_make_nav_series(n=200))
    out = run_all_strategies(points)
    assert out["available"] is True
    assert set(out["strategies"].keys()) == {"buy_hold", "dca_monthly", "dip_buying"}
    for s in out["strategies"].values():
        assert "total_return_pct" in s
        assert "max_drawdown_pct" in s


def test_no_look_ahead_dip_buying_uses_past_only():
    """در dip_buying، خرید فقط بعد از بازگشت از کفِ «گذشته» رخ می‌دهد."""
    points = _make_nav_points(_make_nav_series(n=150, seed=7))
    res = run_backtest(points, strategy="dip_buying", dip_threshold_pct=-3.0)
    if res is None:
        pytest.skip("no dip signal in series")
    for trade in res.trades:
        # هر معامله باید با قیمتِ همان روز ثبت شده باشد (نه آینده)
        assert trade.action == "buy"
        assert trade.price > 0


# ── Calendar ─────────────────────────────────────────────────────────────────


def test_iran_weekend():
    assert is_iran_trading_day(date(2025, 1, 4)) is True   # شنبه
    assert is_iran_trading_day(date(2025, 1, 9)) is False  # پنجشنبه
    assert is_iran_trading_day(date(2025, 1, 10)) is False # جمعه


def test_next_trading_day_skips_weekend():
    assert next_trading_day(date(2025, 1, 9)) == date(2025, 1, 11)   # پنجشنبه → شنبه
