"""API boundary: options responses must be JSON-safe (no Infinity/NaN).

``Starlette``'s ``JSONResponse`` serialises with ``allow_nan=False``, so a single
non-finite Greek turns a 200 into a 500 for every consumer. These tests call the
route handlers directly and assert the whole payload survives
``json.dumps(..., allow_nan=False)``.
"""

from __future__ import annotations

import json
from typing import Any

from apps.api.endpoints.options import (
    MarginLeg,
    MarginRequest,
    calculate_greeks,
    check_parity,
    position_margin,
    pricing,
)


def _assert_json_safe(payload: Any) -> None:
    json.dumps(payload, allow_nan=False)


async def test_greeks_endpoint_is_json_safe_for_underflowing_inputs() -> None:
    response = await calculate_greeks(S=100.0, K=100.0, T=1e-300, r=0.2, sigma=1e-300)

    assert response.success is True
    _assert_json_safe(response.model_dump())


async def test_pricing_endpoint_is_json_safe_for_underflowing_inputs() -> None:
    response = await pricing(S=100.0, K=100.0, T=1e-300, r=0.2, sigma=1e-300)

    assert response.success is True
    assert response.data is not None
    assert response.data["call_price"] == 0.0
    assert response.data["put_price"] == 0.0
    _assert_json_safe(response.model_dump())


async def test_margin_endpoint_charges_an_undercovered_position() -> None:
    body = MarginRequest(
        legs=[
            MarginLeg(
                leg_type="stock", direction="long",
                underlying_price=10_000.0, quantity=1_000,  # shares
            ),
            MarginLeg(
                leg_type="call", direction="short", strike=10_500.0, premium=5.0,
                underlying_price=10_000.0, days_to_expiry=30,
                implied_volatility=0.3, quantity=10, contract_size=1_000,
            ),
        ]
    )

    response = await position_margin(body)

    assert response.success is True
    assert response.data is not None
    assert response.data["strategy_type"] != "covered_call"
    assert response.data["total_initial_margin"] > 0
    _assert_json_safe(response.model_dump())


async def test_parity_endpoint_rejects_negative_horizon() -> None:
    response = await check_parity(
        call_price=100.0, put_price=80.0, stock_price=1_000.0,
        strike=1_000.0, time_to_expiry=-1.0,
    )

    assert response.success is False
    assert response.error is not None
    _assert_json_safe(response.model_dump())


async def test_parity_endpoint_is_json_safe() -> None:
    response = await check_parity(
        call_price=120.0, put_price=30.0, stock_price=1_000.0,
        strike=950.0, time_to_expiry=0.25,
    )

    assert response.success is True
    _assert_json_safe(response.model_dump())
