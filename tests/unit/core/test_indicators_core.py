"""Unit tests for core/indicators.py — TDD safety net (P1).

Covers the two previously-untested primitives with hand-computed expectations:
    - compute_trend_strength (up/down day counting, scaled by 1.5)
    - compute_volatility_regime (population std of simple returns × scale, capped at 1)

Plus Wilder-smoothing parity spot-checks for compute_rsi / compute_atr with
exact hand-derived values (seed + recursive smoothing).

Edge cases: insufficient data, flat series, zero/negative previous closes,
window boundaries (only the last *period* days count), and range invariants.
"""

from __future__ import annotations

import math

import pytest

from core.indicators import (
    compute_atr,
    compute_rsi,
    compute_trend_strength,
    compute_volatility_regime,
)

# ── compute_trend_strength ────────────────────────────────────────────────────


class TestTrendStrength:
    PERIOD = 14

    def test_all_up_days_is_maxed_at_one(self) -> None:
        # 15 strictly increasing closes: 14 up days → |14-0|/14 = 1.0 → min(1, 1.5) = 1.0
        closes = [float(i) for i in range(100, 115)]
        assert compute_trend_strength(closes, period=self.PERIOD) == pytest.approx(1.0)

    def test_all_down_days_is_maxed_at_one(self) -> None:
        closes = [float(i) for i in range(115, 100, -1)]
        assert compute_trend_strength(closes, period=self.PERIOD) == pytest.approx(1.0)

    def test_perfectly_alternating_is_zero(self) -> None:
        # 14 days alternating up/down → |7-7|/14 = 0 → min(1, 0×1.5) = 0.0
        closes = [100.0 + (2.0 if i % 2 else 0.0) for i in range(15)]
        assert compute_trend_strength(closes, period=self.PERIOD) == pytest.approx(0.0)

    def test_flat_series_is_half(self) -> None:
        closes = [100.0] * 15
        assert compute_trend_strength(closes, period=self.PERIOD) == pytest.approx(0.5)

    def test_insufficient_data_returns_half(self) -> None:
        # len < period + 1 → neutral 0.5
        assert compute_trend_strength([1.0, 2.0, 3.0], period=self.PERIOD) == pytest.approx(0.5)
        assert compute_trend_strength([], period=self.PERIOD) == pytest.approx(0.5)

    def test_hand_computed_10_up_4_down(self) -> None:
        # period=14: 10 up, 4 down → |10-4|/14 = 6/14 → min(1, 6/14×1.5) = 9/14
        closes: list[float] = [100.0]
        value = 100.0
        deltas = [+1.0] * 10 + [-1.0] * 4
        for d in deltas:
            value += d
            closes.append(value)
        assert len(closes) == 15
        assert compute_trend_strength(closes, period=self.PERIOD) == pytest.approx(9.0 / 14.0)

    def test_only_last_period_days_count(self) -> None:
        # Old segment (all up) must be ignored; only the last `period` moves matter.
        # Recent window: alternating → strength 0.0 despite strong prior uptrend.
        old = [float(i) for i in range(0, 50)]          # 49 up moves, ignored
        recent = [100.0 + (2.0 if i % 2 else 0.0) for i in range(15)]
        assert compute_trend_strength(old + recent, period=self.PERIOD) == pytest.approx(0.0)

    def test_output_always_within_unit_range(self) -> None:
        closes = [100.0, 101.0, 99.5, 102.0, 101.0, 98.0, 103.0, 100.5, 104.0, 99.0, 105.0, 103.0, 106.0, 102.0, 107.0]
        score = compute_trend_strength(closes, period=self.PERIOD)
        assert 0.0 <= score <= 1.0

    def test_custom_period_respected(self) -> None:
        # period=4 over 5 closes: 3 up, 1 down → |3-1|/4 = 0.5 → min(1, 0.75) = 0.75
        closes = [10.0, 11.0, 12.0, 11.0, 13.0]
        assert compute_trend_strength(closes, period=4) == pytest.approx(0.75)


# ── compute_volatility_regime ─────────────────────────────────────────────────


class TestVolatilityRegime:
    PERIOD = 20

    def test_constant_prices_give_zero_vol(self) -> None:
        closes = [100.0] * 25
        assert compute_volatility_regime(closes, period=self.PERIOD) == pytest.approx(0.0)

    def test_insufficient_data_returns_neutral_half(self) -> None:
        assert compute_volatility_regime([100.0, 101.0], period=self.PERIOD) == pytest.approx(0.5)
        assert compute_volatility_regime([], period=self.PERIOD) == pytest.approx(0.5)

    def test_hand_computed_mild_series(self) -> None:
        # Population std of the 5 simple returns ≈ 0.0097258 → ×20 ≈ 0.194515
        closes = [100.0, 101.0, 102.0, 101.0, 100.0, 99.0]
        score = compute_volatility_regime(closes, period=5)
        assert score == pytest.approx(0.194515, abs=1e-4)

    def test_scale_parameter_maps_five_percent_std_to_one(self) -> None:
        # A series whose return std ≈ 5% with default scale=20 → 0.05×20 = 1.0 (capped)
        closes = [100.0]
        for r in (0.05, -0.05, 0.05, -0.05, 0.05, -0.05, 0.05, -0.05, 0.05, -0.05, 0.05, -0.05, 0.05, -0.05, 0.05, -0.05, 0.05, -0.05, 0.05, -0.05, 0.05):
            closes.append(closes[-1] * (1.0 + r))
        assert compute_volatility_regime(closes, period=self.PERIOD) == pytest.approx(1.0)

    def test_capped_at_one_for_extreme_series(self) -> None:
        closes = [100.0]
        for i in range(1, 25):
            closes.append(closes[-1] * (1.35 if i % 2 else 0.70))
        assert compute_volatility_regime(closes, period=self.PERIOD) == pytest.approx(1.0)

    def test_zero_or_negative_previous_close_is_skipped(self) -> None:
        # Index 5 = 0 sits inside the return window as a *previous* close;
        # the `closes[i-1] > 0` guard must skip that return (no div-by-zero/inf).
        closes = [100.0, 101.0, 102.0, 103.0, 104.0, 0.0, 105.0, 106.0]
        score = compute_volatility_regime(closes, period=5)
        assert math.isfinite(score)
        assert 0.0 <= score <= 1.0

    def test_nonzero_previous_close_required_for_all_returns(self) -> None:
        # Leading zero close: returns computed only from positive previous closes.
        closes = [0.0, 100.0, 102.0, 101.0, 103.0, 102.0, 104.0]
        score = compute_volatility_regime(closes, period=5)
        assert 0.0 < score <= 1.0

    def test_higher_dispersion_scores_higher(self) -> None:
        calm = [100.0, 100.5, 100.2, 100.8, 100.4, 100.6, 100.3, 100.7, 100.5, 100.4, 100.6]
        wild = [100.0, 104.0, 98.0, 106.0, 95.0, 108.0, 94.0, 107.0, 96.0, 105.0, 97.0]
        assert compute_volatility_regime(wild, period=10) > compute_volatility_regime(calm, period=10)

    def test_uses_only_last_period_returns(self) -> None:
        # A violent history outside the window must not affect the score.
        violent_history = [100.0]
        for i in range(1, 21):
            violent_history.append(violent_history[-1] * (1.30 if i % 2 else 0.72))
        calm_recent = [100.0 + (0.1 if i % 2 else -0.1) * i for i in range(22)]
        score_a = compute_volatility_regime(violent_history + calm_recent, period=self.PERIOD)
        score_b = compute_volatility_regime(calm_recent, period=self.PERIOD)
        assert score_a == pytest.approx(score_b)


# ── RSI (Wilder) parity spot-checks ──────────────────────────────────────────


class TestRsiWilderParity:
    def test_all_gains_is_hundred(self) -> None:
        closes = [float(i) for i in range(10, 30)]
        assert compute_rsi(closes, period=14) == pytest.approx(100.0)

    def test_all_losses_is_zero(self) -> None:
        closes = [float(i) for i in range(30, 10, -1)]
        assert compute_rsi(closes, period=14) == pytest.approx(0.0)

    def test_insufficient_data_is_neutral(self) -> None:
        assert compute_rsi([1.0, 2.0, 3.0], period=14) == pytest.approx(50.0)

    def test_hand_computed_wilder_seed_plus_two_steps(self) -> None:
        # closes = [10,11,12,11,10,11], period=3
        # seed: avg_gain=2/3, avg_loss=1/3
        # step1: g=(4/9), l=(5/9)   step2: g=17/27, l=10/27
        # rs=1.7 → rsi = 100 - 100/2.7 = 1700/27
        closes = [10.0, 11.0, 12.0, 11.0, 10.0, 11.0]
        assert compute_rsi(closes, period=3) == pytest.approx(1700.0 / 27.0, abs=1e-9)

    def test_seed_only_boundary_period_plus_one_points(self) -> None:
        # len == period+1 → no smoothing iterations, seed only.
        # deltas [1,1,-1]: avg_gain=2/3, avg_loss=1/3 → rs=2 → 100-100/3
        closes = [10.0, 11.0, 12.0, 11.0]
        assert compute_rsi(closes, period=3) == pytest.approx(100.0 - 100.0 / 3.0, abs=1e-9)


# ── ATR (Wilder) parity spot-checks ──────────────────────────────────────────


class TestAtrWilderParity:
    def test_insufficient_data_returns_none(self) -> None:
        assert compute_atr([1.0, 2.0], [0.5, 1.0], [0.8, 1.5], period=14) is None
        assert compute_atr([], [], [], period=14) is None

    def test_hand_computed_seed_only(self) -> None:
        # TRs = [1.0, 2.0], period=2 → seed (1+2)/2 = 1.5, no smoothing steps.
        highs = [10.0, 11.0, 12.0]
        lows = [9.0, 10.0, 10.0]
        closes = [10.0, 10.5, 11.5]
        assert compute_atr(highs, lows, closes, period=2) == pytest.approx(1.5)

    def test_hand_computed_seed_plus_one_wilder_step(self) -> None:
        # TRs = [1.0, 2.0, 1.0], period=2 → seed 1.5 → Wilder: (1.5×1 + 1.0)/2 = 1.25
        highs = [10.0, 11.0, 12.0, 11.8]
        lows = [9.0, 10.0, 10.0, 10.8]
        closes = [10.0, 10.5, 11.5, 11.0]
        assert compute_atr(highs, lows, closes, period=2) == pytest.approx(1.25)

    def test_true_range_uses_gap_against_prev_close(self) -> None:
        # Down-gap: high=10.5, low=9.5 but prev_close=12 → TR = |9.5-12| = 2.5
        highs = [12.0, 10.5]
        lows = [11.0, 9.5]
        closes = [12.0, 10.0]
        assert compute_atr(highs, lows, closes, period=1) == pytest.approx(2.5)

    def test_atr_is_non_negative(self) -> None:
        highs = [10.0, 9.0, 11.0, 10.5, 12.0]
        lows = [9.0, 8.0, 9.5, 9.8, 10.5]
        closes = [9.5, 8.5, 10.0, 10.2, 11.0]
        atr = compute_atr(highs, lows, closes, period=3)
        assert atr is not None and atr > 0.0
