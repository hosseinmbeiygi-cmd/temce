"""Unit tests for the IME v5.0 Tier 1/2 pricing engine (doc §3.1–§3.4, Appendix ه).

Covers Black-76 reference, Displaced Diffusion, arbitrage-guarded implied vol,
Cubic Spline vol surface, SABR data-sufficiency gate, cost-of-carry futures
and the central config loader.
"""

from __future__ import annotations

import math

import pytest

from core.config.ime_engine import ime_threshold, load_ime_config
from domain.options.commodity_pricing import (
    alpha_floor_verified,
    black76_call,
    black76_put,
    displaced_diffusion_call,
    fair_futures_price,
    futures_mispricing_pct,
    implied_volatility_black76,
    intervention_risk_multiplier,
    price_displaced_diffusion,
    put_call_parity_violation,
)
from domain.options.volatility import cubic_spline_surface_iv, sabr_sufficiency_gate


class TestBlack76Reference:
    def test_atm_call_reference(self):
        """Hull-style reference: F=K=100, T=0.5, r=0.05, σ=0.25 → C ≈ 6.87."""
        F, K, T, r, sigma = 100.0, 100.0, 0.5, 0.05, 0.25
        c = black76_call(F, K, T, r, sigma)
        assert c == pytest.approx(6.87, abs=0.02)

    def test_atm_put_matches_call(self):
        """At F=K the Black-76 put equals the call."""
        F, K, T, r, sigma = 100.0, 100.0, 0.5, 0.05, 0.25
        assert black76_put(F, K, T, r, sigma) == pytest.approx(black76_call(F, K, T, r, sigma), abs=1e-12)

    def test_deep_otm_call_small(self):
        assert black76_call(100, 120, 0.25, 0.05, 0.20) < 1.0


class TestDisplacedDiffusion:
    def test_alpha_zero_equals_black76(self):
        F, K, T, r, sigma = 100.0, 105.0, 0.25, 0.05, 0.30
        assert displaced_diffusion_call(F, K, T, r, sigma, alpha=0.0) == pytest.approx(
            black76_call(F, K, T, r, sigma), abs=1e-12
        )

    def test_alpha_raises_call_price(self):
        """A positive floor shifts moneyness in favour of the call buyer."""
        F, K, T, r, sigma = 100.0, 105.0, 0.25, 0.05, 0.30
        assert displaced_diffusion_call(F, K, T, r, sigma, alpha=10.0) > displaced_diffusion_call(
            F, K, T, r, sigma, alpha=0.0
        )

    def test_tier2_gate_blocks_unverified_alpha(self):
        """α>0 without an official source + timestamp → pricing refused (None)."""
        assert not alpha_floor_verified(alpha=10.0, source=None, has_timestamp=False)
        assert alpha_floor_verified(alpha=10.0, source="ime-announcement", has_timestamp=True)
        assert price_displaced_diffusion(100.0, 105.0, 0.25, 0.05, 0.30, alpha=10.0) is None
        # α=0 needs no official source → allowed
        assert price_displaced_diffusion(100.0, 105.0, 0.25, 0.05, 0.30, alpha=0.0) is not None


class TestImpliedVolatilityBlack76:
    def test_roundtrip(self):
        F, K, T, r, sigma_true = 100.0, 100.0, 0.25, 0.05, 0.35
        price = black76_call(F, K, T, r, sigma_true)
        iv = implied_volatility_black76(price, F, K, T, r, "call")
        assert iv == pytest.approx(sigma_true, abs=1e-3)

    def test_put_roundtrip(self):
        F, K, T, r, sigma_true = 100.0, 95.0, 0.5, 0.05, 0.40
        price = black76_put(F, K, T, r, sigma_true)
        iv = implied_volatility_black76(price, F, K, T, r, "put")
        assert iv == pytest.approx(sigma_true, abs=1e-3)

    def test_parity_violation_returns_null(self):
        """Price above the no-arb upper bound (e^{−rT}·F) → None. سند §3.2."""
        F, K, T, r = 100.0, 100.0, 0.25, 0.05
        upper = math.exp(-r * T) * F
        assert implied_volatility_black76(upper + 0.1, F, K, T, r, "call") is None

    def test_below_lower_bound_returns_null(self):
        """ITM call priced below the discounted intrinsic bound e^{−rT}(F−K) → None."""
        F, K, T, r = 120.0, 100.0, 0.25, 0.05
        lo = math.exp(-r * T) * (F - K)
        assert implied_volatility_black76(lo * 0.5, F, K, T, r, "call") is None

    def test_invalid_inputs_null(self):
        assert implied_volatility_black76(5.0, 100.0, 100.0, 0.0, 0.05) is None
        assert implied_volatility_black76(-1.0, 100.0, 100.0, 0.25, 0.05) is None


class TestPutCallParity:
    def test_consistent_pair_not_violation(self):
        F, K, T, r, sigma = 100.0, 95.0, 0.5, 0.05, 0.25
        c = black76_call(F, K, T, r, sigma)
        p = black76_put(F, K, T, r, sigma)
        assert not put_call_parity_violation(c, p, F, K, T, r)

    def test_inflated_call_is_violation(self):
        F, K, T, r = 100.0, 95.0, 0.5, 0.05
        assert put_call_parity_violation(20.0, 5.0, F, K, T, r)


class TestCubicSplineSurface:
    def test_interpolation_between_strikes(self):
        strikes = [90.0, 100.0, 110.0]
        vols = [0.30, 0.25, 0.32]
        mid = cubic_spline_surface_iv(strikes, vols, query_strike=100.0)
        assert mid == pytest.approx(0.25, abs=1e-6)
        inside = cubic_spline_surface_iv(strikes, vols, query_strike=95.0)
        assert inside is not None and 0.25 <= inside <= 0.32

    def test_out_of_range_returns_none(self):
        strikes = [90.0, 100.0, 110.0]
        vols = [0.30, 0.25, 0.32]
        assert cubic_spline_surface_iv(strikes, vols, query_strike=80.0) is None
        assert cubic_spline_surface_iv(strikes, vols, query_strike=120.0) is None

    def test_too_few_points_returns_none(self):
        assert cubic_spline_surface_iv([90.0, 100.0], [0.30, 0.25], query_strike=95.0) is None


class TestSABRGate:
    def test_sufficient_data_activates(self):
        strikes = {"m1": [90.0, 95.0, 100.0, 105.0, 110.0], "m2": [90.0, 95.0, 100.0, 105.0, 110.0]}
        ok, reasons = sabr_sufficiency_gate(strikes, calibration_rmse=0.01, calibrated_days=20)
        assert ok and not reasons

    def test_one_maturity_fails(self):
        strikes = {"m1": [90.0, 95.0, 100.0, 105.0, 110.0]}
        ok, reasons = sabr_sufficiency_gate(strikes, calibration_rmse=0.01, calibrated_days=20)
        assert not ok
        assert any("maturities" in r for r in reasons)

    def test_high_rmse_fails(self):
        strikes = {"m1": [90.0, 95.0, 100.0, 105.0, 110.0], "m2": [90.0, 95.0, 100.0, 105.0, 110.0]}
        ok, reasons = sabr_sufficiency_gate(strikes, calibration_rmse=0.05, calibrated_days=20)
        assert not ok
        assert any("RMSE" in r for r in reasons)


class TestFuturesCarry:
    def test_fair_futures_price(self):
        fair = fair_futures_price(spot=100.0, risk_free=0.25, carry_cost=0.05, convenience_yield=0.02, T=0.25)
        assert fair == pytest.approx(100.0 * math.exp(0.28 * 0.25), abs=1e-9)

    def test_mispricing_sign(self):
        fair = fair_futures_price(100.0, 0.25, 0.05, 0.02, 0.25)
        assert futures_mispricing_pct(market_futures=fair * 1.05, fair_futures=fair) > 0
        assert futures_mispricing_pct(market_futures=fair * 0.95, fair_futures=fair) < 0

    def test_intervention_risk_multiplier(self):
        floor, ceiling = 100.0, 120.0
        mid = 110.0
        assert intervention_risk_multiplier(mid, floor, ceiling) == pytest.approx(1.0, abs=1e-9)
        near_band = intervention_risk_multiplier(119.5, floor, ceiling)
        assert near_band > intervention_risk_multiplier(115.0, floor, ceiling) > 1.0
        assert intervention_risk_multiplier(121.0, floor, ceiling) == float("inf")
        assert intervention_risk_multiplier(99.0, floor, ceiling) == float("inf")


class TestImeConfig:
    def test_loads_versioned_central_config(self):
        cfg = load_ime_config()
        assert cfg["config_version"] == "1.0.0"
        assert cfg["engine"] == "ime_decision_support"

    def test_threshold_accessor(self):
        cfg = load_ime_config()
        assert ime_threshold(cfg, "iv", "convergence_tolerance") == 0.001
        assert ime_threshold(cfg, "signal_factory", "calendar_arb_ratio_threshold") == pytest.approx(0.95)
        assert ime_threshold(cfg, "sabr", "min_strikes_per_maturity") == 5

    def test_unknown_key_raises(self):
        cfg = load_ime_config()
        with pytest.raises(KeyError):
            ime_threshold(cfg, "nonexistent", "key")
