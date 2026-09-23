"""Endpoint-level tests for POST /options/payoff-calculator."""

from __future__ import annotations

import pytest

from apps.api.endpoints.options import payoff_calculator, router
from schemas.api.options import PayoffCalculatorRequest


def _spec_example_request() -> PayoffCalculatorRequest:
    return PayoffCalculatorRequest.model_validate(
        {
            "legs": [
                {"type": "call", "action": "buy", "strike": 8000, "premium": 650, "quantity": 10},
                {"type": "call", "action": "sell", "strike": 8500, "premium": 300, "quantity": 10},
            ],
            "priceRange": {"min": 6000, "max": 11000, "step": 100},
        }
    )


def test_payoff_calculator_route_registered() -> None:
    assert "/payoff-calculator" in {route.path for route in router.routes}
    assert "/live/chain/{underlying}" in {route.path for route in router.routes}
    assert "/strategies" in {route.path for route in router.routes}


async def test_payoff_calculator_matches_spec_example() -> None:
    response = await payoff_calculator(_spec_example_request())
    assert response.success is True
    assert response.data is not None
    assert response.data["breakEvenPoints"] == pytest.approx([8350])
    assert response.data["maxProfit"] == pytest.approx(1_500_000)
    assert response.data["maxLoss"] == pytest.approx(-3_500_000)
    assert response.data["maxProfitUnbounded"] is False
    assert response.data["maxLossUnbounded"] is False
    assert response.data["payoffCurve"][0] == {"price": 6000, "payoff": pytest.approx(-3_500_000)}
    assert response.data["payoffCurve"][-1] == {"price": 11000, "payoff": pytest.approx(1_500_000)}


async def test_payoff_calculator_rejects_invalid_range() -> None:
    request = PayoffCalculatorRequest.model_validate(
        {
            "legs": [{"type": "call", "action": "buy", "strike": 100, "premium": 10, "quantity": 1}],
            "priceRange": {"min": 100, "max": 100, "step": 10},
        }
    )
    response = await payoff_calculator(request)
    assert response.success is False
    assert response.error is not None
    assert "price_max" in response.error["message"]


async def test_payoff_calculator_supports_contract_size_override() -> None:
    payload = _spec_example_request().model_dump(by_alias=True)
    payload["contractSize"] = 1
    request = PayoffCalculatorRequest.model_validate(payload)
    response = await payoff_calculator(request)
    assert response.success is True
    assert response.data is not None
    assert response.data["payoffCurve"][0]["payoff"] == pytest.approx(-3500)
    assert response.data["maxLoss"] == pytest.approx(-3500)
