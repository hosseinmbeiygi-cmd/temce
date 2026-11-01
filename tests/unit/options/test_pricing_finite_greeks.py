"""FIN: Black-Scholes output must always be finite and JSON-safe.

``sigma * sqrt(T)`` can underflow to exactly 0 even though both inputs are
positive (``sigma=1e-300, T=1e-300``); the old guard only checked the inputs
and ``_d1`` then raised ZeroDivisionError. Extreme parameters can also overflow
theta. Both cases used to crash the pricing endpoint or emit ``Infinity``,
which ``json.dumps(allow_nan=False)`` (Starlette JSONResponse) rejects.
"""

from __future__ import annotations

import json
import math

import pytest

from domain.options.pricing import (
    black_scholes_call,
    black_scholes_price,
    black_scholes_put,
)

EXTREME_PARAMS = [
    (100.0, 100.0, 0.001, 0.2, 1e-4),      # report 2.5: tiny sigma
    (100.0, 100.0, 1e-8, 0.2, 1e-8),       # near-expiry, near-zero vol
    (100.0, 100.0, 1e-300, 0.2, 1e-300),   # sigma*sqrt(T) underflows to 0.0
    (100.0, 1e6, 1e-3, 0.2, 1e-3),         # deep OTM
    (100.0, 1e-6, 1e-3, 0.2, 1e-3),        # deep ITM
    (100.0, 100.0, 5e-324, 0.2, 5.0),      # subnormal T, high vol
    (100.0, 100.0, 1.0, 0.2, 0.9),         # normal but high vol
]


@pytest.mark.parametrize("S,K,T,r,sigma", EXTREME_PARAMS)
@pytest.mark.parametrize("option_type", ["call", "put"])
def test_greeks_are_finite_and_json_serialisable(S, K, T, r, sigma, option_type) -> None:
    op = black_scholes_price(S, K, T, r, sigma, option_type)

    payload = {
        "price": op.price,
        "delta": op.delta,
        "gamma": op.gamma,
        "theta": op.theta,
        "vega": op.vega,
        "rho": op.rho,
        "intrinsic": op.intrinsic_value,
        "time_value": op.time_value,
    }
    for name, value in payload.items():
        assert math.isfinite(value), f"{name} is not finite: {value!r}"
    json.dumps(payload, allow_nan=False)  # raises on inf/NaN


def test_underflowing_vol_sqrt_t_does_not_divide_by_zero() -> None:
    """Regression: positive sigma and T whose product underflows to 0.0."""
    assert black_scholes_call(100.0, 100.0, 1e-300, 0.2, 1e-300) == 0.0
    assert black_scholes_put(100.0, 100.0, 1e-300, 0.2, 1e-300) == 0.0


@pytest.mark.parametrize(
    ("S", "K", "T", "r", "sigma"),
    [
        (100.0, 100.0, 1.0, 0.2, 0.25),
        (100.0, 120.0, 0.5, 0.1, 0.40),
        (5_000.0, 4_500.0, 0.25, 0.30, 0.60),
    ],
)
def test_put_call_parity(S, K, T, r, sigma) -> None:
    """C - P = S - K·e^{-rT} for European options on a non-dividend asset."""
    call = black_scholes_call(S, K, T, r, sigma)
    put = black_scholes_put(S, K, T, r, sigma)

    assert call - put == pytest.approx(S - K * math.exp(-r * T), abs=1e-9)


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_expired_option_falls_back_to_intrinsic(option_type) -> None:
    itm = black_scholes_price(110.0, 100.0, 0.0, 0.2, 0.3, option_type)
    otm = black_scholes_price(90.0, 100.0, 0.0, 0.2, 0.3, option_type)

    assert itm.price == (10.0 if option_type == "call" else 0.0)
    assert otm.price == (0.0 if option_type == "call" else 10.0)
    assert itm.gamma == otm.gamma == 0.0
