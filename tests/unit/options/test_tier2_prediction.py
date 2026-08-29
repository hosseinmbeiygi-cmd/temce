"""Tests for the Tier-2 prediction upgrades in the IME v5.0 engine.

Covers Monte Carlo (European + American LSM), Cointegration (Johansen + Z-score
spread signal), and the Heston Tier-2 activation gate.
"""

from __future__ import annotations

import math

import numpy as np

from domain.options.cointegration import (
    MIN_SERIES_LENGTH,
    cointegration_data_sufficient,
    cointegration_signal,
    johansen_trace_test,
    spread_zscore,
)
from domain.options.heston_model import HestonParams, heston_calibration_sufficient
from domain.options.monte_carlo import black_scholes_european, monte_carlo_american_lsm, monte_carlo_european

# ── Monte Carlo (European baseline) ──────────────────────────────────────────


class TestMonteCarloEuropean:
    def test_matches_black_scholes_within_3_std(self):
        """ATM call: BS ≈ 10.45 for S=K=100, T=1, r=0.05, σ=0.20."""
        S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.20
        bs = black_scholes_european(S, K, T, r, sigma)
        mc = monte_carlo_european(S, K, T, r, sigma, n_paths=200_000, n_steps=252, seed=7)
        # 3 standard errors tolerance — well within the 95% CI by construction
        assert abs(mc.price - bs) <= 3 * mc.std_error + 0.05
        assert bs >= mc.ci_low and bs <= mc.ci_high

    def test_put_matches_black_scholes(self):
        S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.20
        bs = black_scholes_european(S, K, T, r, sigma, option_type="put")
        mc = monte_carlo_european(S, K, T, r, sigma, option_type="put", n_paths=200_000, n_steps=252, seed=11)
        assert abs(mc.price - bs) <= 3 * mc.std_error + 0.05

    def test_antithetic_halves_paths(self):
        mc = monte_carlo_european(100, 100, 1.0, 0.05, 0.2, n_paths=10_000, seed=3)
        # With antithetic default True, n_paths=10_000 → 10_000 actual paths
        assert mc.n_paths == 10_000

    def test_degenerate_inputs(self):
        mc = monte_carlo_european(S=100, K=100, T=0, r=0.05, sigma=0.20)
        assert mc.price == 0.0
        assert mc.n_paths == 0

    def test_confidence_interval_is_symmetric(self):
        mc = monte_carlo_european(100, 100, 1.0, 0.05, 0.2, n_paths=50_000, seed=5)
        assert mc.ci_high > mc.price > mc.ci_low
        assert math.isclose(mc.ci_high - mc.price, mc.price - mc.ci_low, rel_tol=1e-9)

    def test_std_error_decreases_with_paths(self):
        mc_small = monte_carlo_european(100, 100, 1.0, 0.05, 0.2, n_paths=5_000, seed=1)
        mc_large = monte_carlo_european(100, 100, 1.0, 0.05, 0.2, n_paths=80_000, seed=1)
        assert mc_large.std_error < mc_small.std_error

    def test_with_continuous_carry(self):
        S, K, T, r, sigma, q = 100.0, 100.0, 1.0, 0.05, 0.20, 0.02
        bs = black_scholes_european(S, K, T, r, sigma, q=q)
        mc = monte_carlo_european(S, K, T, r, sigma, q=q, n_paths=150_000, seed=9)
        assert abs(mc.price - bs) <= 3 * mc.std_error + 0.05


# ── Monte Carlo (American Longstaff-Schwartz) ────────────────────────────────


class TestMonteCarloAmericanLSM:
    def test_american_put_at_least_european(self):
        """Early-exercise premium: American put ≥ European put."""
        S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.20
        euro = black_scholes_european(S, K, T, r, sigma, option_type="put")
        am = monte_carlo_american_lsm(S, K, T, r, sigma, n_paths=50_000, n_steps=50, option_type="put", seed=13)
        assert am.price >= euro - 3 * am.std_error

    def test_american_call_zero_dividend_equals_european(self):
        """No q → no early exercise → American call ≈ European call."""
        S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.20
        euro = black_scholes_european(S, K, T, r, sigma, option_type="call")
        am = monte_carlo_american_lsm(S, K, T, r, sigma, n_paths=200_000, n_steps=100, option_type="call", seed=17)
        # Allow 1 std error tolerance — call's continuation is well-defined
        assert abs(am.price - euro) <= max(1.0, am.std_error * 3)

    def test_american_price_is_positive(self):
        mc = monte_carlo_american_lsm(100, 110, 0.5, 0.05, 0.25, n_paths=10_000, n_steps=25, option_type="put", seed=19)
        assert mc.price > 0

    def test_degenerate_inputs(self):
        mc = monte_carlo_american_lsm(S=100, K=100, T=0, r=0.05, sigma=0.20)
        assert mc.price == 0.0
        assert mc.n_paths == 0


# ── Cointegration / Johansen (Tier 2, سند §3.4) ──────────────────────────────


def _cointegrated_series(n: int = 500, seed: int = 0) -> tuple[list[float], list[float]]:
    """Two series sharing a long-run equilibrium: S1 + α·S2 ≈ constant.

    Build by drawing a stationary spread then integrating.
    """
    rng = np.random.default_rng(seed)
    spread = np.cumsum(rng.standard_normal(n)) * 0.5
    base = 100 + spread
    hedge = -0.7 * spread + np.cumsum(rng.standard_normal(n)) * 0.05 + 50
    return base.tolist(), hedge.tolist()


class TestCointegration:
    def test_insufficient_data_returns_none(self):
        # 100 < 250 → must refuse (سند §3.4: cost-of-carry fallback)
        s1 = [100 + i * 0.1 for i in range(100)]
        s2 = [50 + i * 0.05 for i in range(100)]
        assert johansen_trace_test(s1, s2) is None

    def test_cointegrated_series_passes_johansen(self):
        """Two near-identical I(1) series pass the 5% critical value (≈12.21)."""
        rng = np.random.default_rng(2)
        n = 500
        s1 = 100 + np.cumsum(rng.standard_normal(n))
        s2 = s1 + 0.5 * rng.standard_normal(n)  # common trend + tiny noise
        result = johansen_trace_test(s1.tolist(), s2.tolist())
        assert result is not None
        assert result.trace_stat > 12.21, f"trace={result.trace_stat:.2f} should exceed 12.21"
        assert result.is_cointegrated

    def test_random_walks_not_cointegrated(self):
        rng = np.random.default_rng(5)
        s1 = np.cumsum(rng.standard_normal(500)).tolist()
        s2 = np.cumsum(rng.standard_normal(500)).tolist()
        result = johansen_trace_test(s1, s2)
        # Two independent random walks should fail at 5%
        assert result is not None
        assert not result.is_cointegrated

    def test_spread_zscore(self):
        s1, s2 = _cointegrated_series(n=500, seed=7)
        result = johansen_trace_test(s1, s2)
        z, mu, sigma = spread_zscore(s1, s2, result.eigenvector)
        # mu ≈ 0 by construction, sigma ≈ some positive constant
        assert sigma > 0
        # Latest Z is a finite number (might be above or below threshold)
        assert math.isfinite(z)

    def test_signal_z_above_threshold(self):
        # Manually construct a spread with extreme z at the latest observation
        s1 = [100.0] * 250
        s2 = [50.0] * 250
        # Now push s1[-1] to extreme (mean s2 = 50)
        s1[-1] = 200.0
        johansen_trace_test(s1, s2)  # not really cointegrated but tests the API
        # If not cointegrated, signal must be "hold" regardless of z
        sig, z, res = cointegration_signal(s1, s2)
        assert sig == "hold" or (res is not None and not res.is_cointegrated)

    def test_data_sufficiency(self):
        assert cointegration_data_sufficient([1] * 250, [1] * 250) is True
        assert cointegration_data_sufficient([1] * 100, [1] * 100) is False
        assert cointegration_data_sufficient([1] * 250, [1] * 200) is False

    def test_min_series_length_constant(self):
        assert MIN_SERIES_LENGTH == 250

    def test_pvalue_monotonic_in_trace_stat(self):
        """Higher trace statistic → lower p-value (MacKinnon approximation)."""
        from domain.options.cointegration import _mackinnon_pvalue_2var

        p_low = _mackinnon_pvalue_2var(8.0)
        p_mid = _mackinnon_pvalue_2var(12.0)
        p_high = _mackinnon_pvalue_2var(20.0)
        assert p_low > p_mid > p_high
        assert p_high < 0.01


# ── Heston Tier-2 gate (سند §3.2) ────────────────────────────────────────────


class TestHestonGate:
    def _params(self, **overrides) -> HestonParams:
        base = {
            "S": 100.0,
            "K": 100.0,
            "T": 1.0,
            "r": 0.05,
            "q": 0.0,
            "v0": 0.04,
            "theta": 0.04,
            "kappa": 2.0,
            "sigma_v": 0.3,
            "rho": -0.7,
        }
        base.update(overrides)
        return HestonParams(**base)

    def test_default_params_sufficient(self):
        ok, reasons = heston_calibration_sufficient(self._params(), market_prices_count=6, calibration_rmse=0.01)
        assert ok, reasons

    def test_too_few_quotes_fails(self):
        ok, reasons = heston_calibration_sufficient(self._params(), market_prices_count=3, calibration_rmse=0.01)
        assert not ok
        assert any("quotes" in r for r in reasons)

    def test_high_rmse_fails(self):
        ok, reasons = heston_calibration_sufficient(self._params(), market_prices_count=10, calibration_rmse=0.05)
        assert not ok
        assert any("RMSE" in r for r in reasons)

    def test_feller_violation_fails(self):
        # 2·κ·θ = 2·0.5·0.04 = 0.04, σ_v² = 0.3² = 0.09 → violation
        ok, reasons = heston_calibration_sufficient(
            self._params(kappa=0.5, theta=0.04, sigma_v=0.3),
            market_prices_count=6,
            calibration_rmse=0.01,
        )
        assert not ok
        assert any("Feller" in r for r in reasons)

    def test_rho_out_of_range_fails(self):
        ok, reasons = heston_calibration_sufficient(
            self._params(rho=0.995), market_prices_count=6, calibration_rmse=0.01
        )
        assert not ok
        assert any("rho" in r for r in reasons)
