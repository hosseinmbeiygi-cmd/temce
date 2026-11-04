"""تست اندیکاتورهای trailing — یکی از دو تست اجباری بخش ۸ گزارش (C2)."""

from __future__ import annotations

import numpy as np
import pytest

from src.gold_desk.indicators import bubble_pct, ema, rsi, sma


def _ramp(n: int = 60, start: float = 100.0, step: float = 1.0) -> list[float]:
    return [start + i * step for i in range(n)]


# ── SMA: فقط گذشته ─────────────────────────────────────────────


def test_sma30_is_trailing_mean():
    """تست اجباری C2: sma30[i] == mean(prices[i-29:i+1]) — نه پنجرهٔ centered."""
    prices = _ramp(60)
    out = sma(prices, 30)
    for i in (29, 40, 59):
        assert out[i] == pytest.approx(float(np.mean(prices[i - 29 : i + 1])))


def test_sma30_matches_audit_number():
    """همان عددی که گزارش ۰۱ برای i=40 محاسبه کرد: ۱۲۵.۵ (convolve: ۱۳۹.۵)."""
    prices = _ramp(60)  # 100..159
    assert sma(prices, 30)[40] == pytest.approx(125.5)


def test_sma_short_input_is_nan():
    out = sma(_ramp(10), 30)
    assert np.isnan(out).all()


def test_sma_no_lookahead_under_future_perturbation():
    prices = _ramp(60)
    base = sma(prices, 30)
    perturbed = list(prices)
    perturbed[50] = 10_000.0  # تغییر آینده
    other = sma(perturbed, 30)
    assert np.allclose(base[:50], other[:50], equal_nan=True)
    assert base[50] != other[50]


# ── EMA ────────────────────────────────────────────────────────


def test_ema_warmup_nan_and_reacts_to_last_value():
    out = ema(_ramp(40), 14)
    assert np.isnan(out[:13]).all()
    assert not np.isnan(out[13:]).any()
    # EMA در انتهای سری صعودی باید نزدیک انتها باشد
    assert out[-1] > 30.0


def test_ema_short_input_is_nan():
    assert np.isnan(ema(_ramp(5), 14)).all()


# ── RSI ────────────────────────────────────────────────────────


def test_rsi_series_is_trailing_and_monotone_scores_100():
    out = rsi(_ramp(40), 14)
    assert np.isnan(out[:14]).all()
    assert out[-1] == pytest.approx(100.0)


def test_rsi_flat_series_is_neutral():
    out = rsi([100.0] * 40, 14)
    assert out[-1] == pytest.approx(50.0)


def test_rsi_short_input_is_nan():
    assert np.isnan(rsi(_ramp(10), 14)).all()


# ── حباب ───────────────────────────────────────────────────────


def test_bubble_uses_trailing_window_only():
    prices = _ramp(60)
    out = bubble_pct(prices, 30)
    assert np.isnan(out[:29]).all()
    mean_40 = float(np.mean(prices[11:41]))
    assert out[40] == pytest.approx((prices[40] - mean_40) / mean_40 * 100.0)


def test_bubble_short_input_is_nan():
    assert np.isnan(bubble_pct(_ramp(10), 30)).all()
