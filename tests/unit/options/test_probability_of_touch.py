"""Probability of touch must match the reflection principle for GBM barriers.

Audit FIN-02. ``probability_of_touch_brownian`` used
``N(d+) + (target/S)^(2μ·ln(target/S)/σ²)·N(-d-)``. Two independent errors:
the normal-CDF terms were swapped and the exponent carried an extra
``ln(target/S)``, so the barrier factor was raised to the wrong power.

Checks:
  * zero log-drift identity ``P = 2·N(-ln(B/S)/(σ√T))`` (exact, no constants),
  * agreement with the module's own Monte Carlo estimator (different method),
  * both barrier directions.
"""

from __future__ import annotations

import math

import pytest
from scipy import stats

from domain.options.probability import (
    probability_of_touch_brownian,
    probability_of_touch_monte_carlo,
)


def test_zero_drift_matches_reflection_identity() -> None:
    """With μ = r - q - σ²/2 = 0, P(max ≥ B) = 2·N(-u/(σ√T))."""
    S, B, T, sigma = 100.0, 110.0, 1.0, 0.2
    r, q = 0.02, 0.0  # μ = 0.02 - 0.02 = 0
    u = math.log(B / S)
    expected = 2.0 * stats.norm.cdf(-u / (sigma * math.sqrt(T)))

    prob = probability_of_touch_brownian(S, B, T, r, sigma, q)

    assert prob == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize(
    ("S", "target", "T", "r", "q", "sigma"),
    [
        (100.0, 110.0, 1.0, 0.0, 0.0, 0.20),
        (100.0, 120.0, 0.25, 0.05, 0.0, 0.30),
        (100.0, 90.0, 0.25, 0.05, 0.0, 0.30),
        (100.0, 80.0, 1.0, 0.02, 0.01, 0.25),
    ],
)
def test_matches_monte_carlo(S, target, T, r, q, sigma) -> None:
    analytic = probability_of_touch_brownian(S, target, T, r, sigma, q)
    simulated = probability_of_touch_monte_carlo(
        S, target, T, r, sigma, q, n_paths=40_000, n_steps=500, seed=7
    )

    # Discrete monitoring in the simulation misses intrabar touches, so the
    # Monte Carlo estimate sits slightly below the continuous-barrier value.
    assert analytic == pytest.approx(simulated, abs=0.02, rel=0.05), (
        f"analytic={analytic:.4f} simulated={simulated:.4f}"
    )


def test_upper_and_lower_barriers_are_symmetric_at_zero_drift() -> None:
    S, T, sigma = 100.0, 0.5, 0.25
    r, q = 0.03125, 0.0  # μ = 0.03125 - 0.03125 = 0

    up = probability_of_touch_brownian(S, 110.0, T, r, sigma, q)
    down = probability_of_touch_brownian(S, 100.0**2 / 110.0, T, r, sigma, q)

    assert up == pytest.approx(down, abs=1e-9)


def test_target_equal_to_spot_is_certain() -> None:
    assert probability_of_touch_brownian(100.0, 100.0, 0.5, 0.05, 0.2) == 1.0


@pytest.mark.parametrize(
    ("S", "target", "T", "sigma"),
    [(100.0, 110.0, 0.0, 0.2), (100.0, 110.0, 0.5, 0.0), (0.0, 110.0, 0.5, 0.2)],
)
def test_degenerate_inputs_return_zero(S, target, T, sigma) -> None:
    assert probability_of_touch_brownian(S, target, T, 0.05, sigma) == 0.0


def test_probability_stays_within_bounds() -> None:
    for target in (60.0, 80.0, 95.0, 105.0, 120.0, 200.0):
        prob = probability_of_touch_brownian(100.0, target, 0.25, 0.05, 0.3)
        assert 0.0 <= prob <= 1.0
