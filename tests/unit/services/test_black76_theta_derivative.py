"""Theta must be the time derivative of the price it is reported with.

Audit FIN-01. ``calculate_greeks`` returned a theta that did not equal
``-dV/dT``: the call branch carried an extra ``+ r·F·e^{-rT}·N(d1)`` term, and
the put branch had the ``r·V`` carry term with the wrong sign. For
``F=K=100, T=0.25, r=0.30, σ=0.25`` that produced ``+0.0109/day`` where the
price derivative is ``-0.0215/day`` — a sign flip in normal regimes.

The finite-difference check below is deliberately independent of any closed
form: it only requires theta to agree with the price the engine itself returns.
"""

from __future__ import annotations

import pytest

from services.gold.black76_engine import black76_price, calculate_greeks

CASES = [
    (100.0, 100.0, 0.5, 0.03, 0.25),
    (100.0, 90.0, 1.0, 0.05, 0.20),
    (100.0, 110.0, 0.25, 0.10, 0.35),
    (1000.0, 1200.0, 0.1, 0.15, 0.60),
    (100.0, 100.0, 0.25, 0.30, 0.25),
]

H = 1e-5


@pytest.mark.parametrize(("F", "K", "T", "r", "sigma"), CASES)
@pytest.mark.parametrize("option_type", ["call", "put"])
def test_theta_equals_minus_dv_dt(F, K, T, r, sigma, option_type) -> None:
    up = black76_price(F, K, T + H, r, sigma, option_type)
    down = black76_price(F, K, T - H, r, sigma, option_type)
    finite_difference = -(up - down) / (2.0 * H)

    theta = calculate_greeks(F, K, T, r, sigma, option_type)["theta"]

    assert theta == pytest.approx(finite_difference, abs=1e-4), (
        f"{option_type} theta={theta:.6f} but -dV/dT={finite_difference:.6f}"
    )


def test_theta_daily_is_theta_over_365() -> None:
    g = calculate_greeks(100.0, 100.0, 0.5, 0.03, 0.25, "call")

    assert g["theta_daily"] == pytest.approx(g["theta"] / 365.0)
