"""Unit tests for _composite_buy_score — the single source of truth for the
currency/gold composite signal (RSI + momentum + trend + volume/activity
proxy + ATR volatility filter).

Pure function tests: no DB, no async I/O. Guards the behavior measured in the
5-candle accuracy benchmark and the live multi_market_signal_engine.
"""
from __future__ import annotations

import pytest

from services.multi_market_signal_engine import _composite_buy_score

BUY_THRESHOLD = 0.15
SELL_THRESHOLD = -0.15


def _flat_series(n: int = 25, price: float = 100.0) -> list[float]:
    return [price] * n


def _score(closes, highs=None, lows=None, tf_days=5, volumes=None, market=""):
    highs = highs if highs is not None else closes
    lows = lows if lows is not None else closes
    return _composite_buy_score(closes, highs, lows, tf_days, volumes, market)


class TestShortSeries:
    """len(closes) < tf_days + 1 must return a neutral score with no reasons."""

    def test_returns_neutral_score_when_series_too_short(self):
        closes = [100.0, 101.0, 102.0, 103.0, 104.0]  # 5 rows, tf_days=5 needs 6
        assert _score(closes, tf_days=5) == (0.0, [])

    def test_single_row_returns_neutral(self):
        assert _score([100.0], tf_days=1) == (0.0, [])


class TestRsi:
    def test_overbought_penalizes_and_adds_reason(self):
        # Strictly rising 25-bar series → RSI=100 (>70) → -0.25.
        # momentum > 0.55 (+0.25) and trend up (+0.15) also fire.
        closes = [100.0 + i for i in range(25)]
        score, reasons = _score(closes, tf_days=5)
        assert any("RSI اشباع خرید" in r for r in reasons)
        assert score == pytest.approx(0.15)  # 0.25 (mom) - 0.25 (rsi) + 0.15 (trend)

    def test_oversold_boosts_and_adds_reason(self):
        # Strictly falling 25-bar series → RSI=0 (<35) → +0.30.
        closes = [200.0 - i for i in range(25)]
        score, reasons = _score(closes, tf_days=5)
        assert any("RSI اشباع فروش" in r for r in reasons)
        assert score == pytest.approx(-0.10)  # -0.25 (mom) + 0.30 (rsi) - 0.15 (trend)

    def test_neutral_rsi_gives_small_bonus_and_stays_hold(self):
        # Alternating ±1 → RSI ≈ 50 (in 40-60) → +0.05. Below the buy threshold.
        closes = [100.0 if i % 2 == 0 else 101.0 for i in range(22)]
        score, reasons = _score(closes, tf_days=1)
        assert score == pytest.approx(0.05)
        assert reasons == []
        assert score <= BUY_THRESHOLD  # neutral → hold


class TestMomentum:
    def test_positive_momentum_reason_and_boost(self):
        # Minimal 2-bar series isolates momentum: RSI neutral (+0.05), flat trend.
        closes = [100.0, 103.0]  # +3% → momentum 0.575 (> 0.55)
        score, reasons = _score(closes, tf_days=1)
        assert any("مومنتوم 1d مثبت" in r for r in reasons)
        assert score == pytest.approx(0.30)  # 0.25 (mom) + 0.05 (rsi neutral)
        assert score > BUY_THRESHOLD

    def test_negative_momentum_reason_and_penalty(self):
        closes = [100.0, 97.0]  # -3% → momentum 0.425 (< 0.45)
        score, reasons = _score(closes, tf_days=1)
        assert any("مومنتوم 1d منفی" in r for r in reasons)
        assert score == pytest.approx(-0.20)  # -0.25 (mom) + 0.05 (rsi neutral)
        assert score < SELL_THRESHOLD


class TestTrend:
    def test_up_trend_reason(self):
        # Step from 100 to 105 keeps momentum flat while MA5 (105) >> MA20 (102.5).
        closes = [100.0] * 15 + [105.0] * 10
        score, reasons = _score(closes, tf_days=5)
        assert any("روند صعودی (MA5>MA20)" in r for r in reasons)
        assert score == pytest.approx(-0.10)  # -0.25 (rsi) + 0.15 (trend)

    def test_down_trend_reason(self):
        # Steadily falling series → MA5 << MA20 (down) and RSI=0 (oversold).
        closes = [200.0 - i * 0.5 for i in range(25)]
        score, reasons = _score(closes, tf_days=5)
        assert any("روند نزولی (MA5<MA20)" in r for r in reasons)
        assert score == pytest.approx(0.15)  # +0.30 (rsi oversold) - 0.15 (trend)


class TestVolatilityFilter:
    def test_high_atr_forces_hold_for_currency(self):
        # Flat closes with ±20% daily ranges → ATR ~40 → 40% > 3% → force hold.
        closes = _flat_series(20)
        highs = [120.0] * 20
        lows = [80.0] * 20
        score, reasons = _score(closes, highs, lows, tf_days=1, market="currency")
        assert score == 0.0
        assert any("نوسان بالا" in r for r in reasons)

    def test_high_atr_forces_hold_for_gold(self):
        closes = _flat_series(20)
        highs = [120.0] * 20
        lows = [80.0] * 20
        score, reasons = _score(closes, highs, lows, tf_days=1, market="gold")
        assert score == 0.0
        assert any("نوسان بالا" in r for r in reasons)

    def test_filter_skipped_for_other_markets(self):
        # Same data with market="" → filter must NOT fire; normal scoring applies.
        closes = _flat_series(20)
        highs = [120.0] * 20
        lows = [80.0] * 20
        score, reasons = _score(closes, highs, lows, tf_days=1, market="")
        assert not any("نوسان بالا" in r for r in reasons)
        assert score == pytest.approx(-0.30)  # -0.25 (rsi=100) - 0.05 (volume proxy ↓)


class TestVolume:
    def test_rising_real_volumes_boost(self):
        closes = _flat_series(25)
        volumes = [1000.0] * 20 + [2500.0] * 5  # short/long ≈ 1.82 → > 0.6
        score, reasons = _score(closes, tf_days=1, volumes=volumes)
        assert any("افزایش حجم/فعالیت" in r for r in reasons)
        assert score == pytest.approx(-0.15)  # -0.25 (rsi) + 0.10 (volume)

    def test_falling_real_volumes_penalize(self):
        closes = _flat_series(25)
        volumes = [2500.0] * 20 + [1000.0] * 5  # short/long ≈ 0.47 → < 0.35
        score, reasons = _score(closes, tf_days=1, volumes=volumes)
        assert any("کاهش حجم/فعالیت" in r for r in reasons)
        assert score == pytest.approx(-0.30)  # -0.25 (rsi) - 0.05 (volume)


class TestCombined:
    def test_momentum_plus_trend_crosses_buy_threshold(self):
        # 25-bar V-shape: falls 150→112, then rallies to 152.
        # momentum(5) = +35.7% (capped) → +0.25; MA5(132) >> MA20(127.5) → +0.15.
        closes = (
            [150.0, 148.0, 146.0, 144.0, 142.0, 140.0, 138.0, 136.0, 134.0, 132.0,
             130.0, 128.0, 126.0, 124.0, 122.0, 120.0, 118.0, 116.0, 114.0, 112.0,
             116.0, 122.0, 130.0, 140.0, 152.0]
        )
        score, reasons = _score(closes, tf_days=5)
        assert any("مومنتوم 5d مثبت" in r for r in reasons)
        assert any("روند صعودی (MA5>MA20)" in r for r in reasons)
        assert score == pytest.approx(0.40)  # 0.25 (mom) + 0.15 (trend)
        assert score > BUY_THRESHOLD
