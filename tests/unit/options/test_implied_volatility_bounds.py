"""IV must be arbitrage-consistent and verified, never a sentinel.

Audit FIN-04. ``implied_volatility`` returned ``0.0`` at expiry and the last
iterate on divergence, with no check against intrinsic/upper bounds; the
options analytics surface displayed those values as valid IV.
"""

from __future__ import annotations

import math

import pytest

from domain.options.pricing import black_scholes_call, black_scholes_put, implied_volatility


def test_round_trips_a_call_volatility() -> None:
    S, K, T, r, sigma = 100.0, 105.0, 0.5, 0.05, 0.35
    price = black_scholes_call(S, K, T, r, sigma)

    assert implied_volatility(price, S, K, T, r, "call") == pytest.approx(sigma, abs=1e-6)


def test_round_trips_a_put_volatility() -> None:
    S, K, T, r, sigma = 100.0, 95.0, 0.25, 0.03, 0.45
    price = black_scholes_put(S, K, T, r, sigma)

    assert implied_volatility(price, S, K, T, r, "put") == pytest.approx(sigma, abs=1e-6)


def test_a_price_below_intrinsic_has_no_solution() -> None:
    S, K, T, r = 110.0, 100.0, 0.25, 0.05
    intrinsic = S - K * math.exp(-r * T)

    assert implied_volatility(intrinsic - 1.0, S, K, T, r, "call") is None


def test_a_price_above_the_upper_bound_has_no_solution() -> None:
    assert implied_volatility(101.0, 100.0, 100.0, 0.5, 0.05, "call") is None


@pytest.mark.parametrize(
    ("price", "S", "K", "T"),
    [(0.0, 100.0, 100.0, 0.5), (-1.0, 100.0, 100.0, 0.5), (5.0, 100.0, 100.0, 0.0)],
)
def test_degenerate_inputs_return_none(price: float, S: float, K: float, T: float) -> None:
    assert implied_volatility(price, S, K, T, 0.05, "call") is None
