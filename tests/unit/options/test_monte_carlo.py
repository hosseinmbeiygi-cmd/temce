"""Tests for Monte Carlo option pricer.

Tolerances are intentionally loose — MC is a stochastic estimator.
The tight checks (zero-T, ATM bounds, sign) protect against logic bugs,
not numerical noise.
"""

from __future__ import annotations

import math

import pytest

from domain.options.monte_carlo import MCResult, monte_carlo_european


def test_intrinsic_at_zero_time() -> None:
    """When T=0, the price must collapse to intrinsic value (no time value)."""
    call = monte_carlo_european(S=110, K=100, T=0, r=0.05, sigma=0.2, n_paths=1000, seed=1)
    assert call.price == pytest.approx(10.0, abs=1e-9)
    assert call.std_error == 0.0

    put = monte_carlo_european(S=90, K=100, T=0, r=0.05, sigma=0.2, n_paths=1000, seed=1, option_type="put")
    assert put.price == pytest.approx(10.0, abs=1e-9)


def test_call_price_within_black_scholes_band() -> None:
    """MC call should land within ±3% of analytic Black-Scholes for vanilla ATM.

    Loose on purpose — 10k paths gives ~1% std error; 3σ guard = 3%.
    """
    S = K = 100.0
    T, r, sigma = 1.0, 0.05, 0.2
    # Analytic Black-Scholes for ATM call
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    bs_price = S * 0.5 * (1 + math.erf(d1 / math.sqrt(2))) - K * math.exp(-r * T) * 0.5 * (
        1 + math.erf(d2 / math.sqrt(2))
    )

    mc = monte_carlo_european(S=S, K=K, T=T, r=r, sigma=sigma, n_paths=50_000, seed=42)
    # 3% band, generous because we want a robust test, not a numerics torture.
    assert abs(mc.price - bs_price) / bs_price < 0.03, f"MC {mc.price} vs BS {bs_price}"


def test_put_call_parity_holds() -> None:
    """C - P = S*exp(-q*T) - K*exp(-r*T). With q=0: C - P = S - K*exp(-r*T)."""
    S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.2
    call = monte_carlo_european(S=S, K=K, T=T, r=r, sigma=sigma, n_paths=50_000, seed=42, option_type="call")
    put = monte_carlo_european(S=S, K=K, T=T, r=r, sigma=sigma, n_paths=50_000, seed=42, option_type="put")
    parity = S - K * math.exp(-r * T)
    # Each side has ~1% MC noise; combined ~1.5%; allow 3%.
    assert abs((call.price - put.price) - parity) < 0.3


def test_confidence_interval_contains_price() -> None:
    mc = monte_carlo_european(S=100, K=100, T=1, r=0.05, sigma=0.2, n_paths=20_000, seed=7)
    assert isinstance(mc, MCResult)
    assert mc.ci_low < mc.price < mc.ci_high
    assert mc.ci_high - mc.price == pytest.approx(mc.price - mc.ci_low, abs=1e-9)
    # 95% CI ⇒ half-width ≈ 1.96 × std_error
    assert (mc.ci_high - mc.price) == pytest.approx(1.96 * mc.std_error, rel=1e-6)


def test_invalid_inputs_return_intrinsic() -> None:
    """Negative T or sigma must short-circuit to intrinsic value, not error."""
    r = monte_carlo_european(S=100, K=100, T=-1, r=0.05, sigma=0.2, seed=1)
    assert r.price == 0.0  # ATM at negative T → no time value, no intrinsic
    r = monte_carlo_european(S=100, K=100, T=1, r=0.05, sigma=0.0, seed=1)
    assert r.price == 0.0  # ATM, zero vol → no time value
