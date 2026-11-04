"""Additive calendar-spread and roll-yield coverage for the futures curve."""

from __future__ import annotations

import pytest

from services.gold.futures_term import analyze_futures_curve


def _contract(symbol: str, days: float, price: float) -> dict:
    return {
        "contract_symbol": symbol,
        "days_to_expiry": days,
        "futures_price": price,
    }


def test_calendar_spread_and_roll_yield_are_additive():
    result = analyze_futures_curve(
        100.0,
        [
            _contract("NEAR", 30.0, 102.0),
            _contract("FAR", 90.0, 106.0),
        ],
    )

    # Existing outputs remain intact.
    assert result["front_contract"]["symbol"] == "NEAR"
    assert result["contracts"][0]["basis"] == pytest.approx(2.0)
    assert result["contracts"][1]["basis"] == pytest.approx(6.0)

    near, far = result["contracts"]
    assert near["next_contract_symbol"] == "FAR"
    assert far["next_contract_symbol"] is None

    # roll_yield = (near - far) / far = (102 - 106) / 106
    expected_roll = (102.0 - 106.0) / 106.0
    assert near["roll_yield"] == pytest.approx(expected_roll)
    assert near["roll_yield_pct"] == pytest.approx(expected_roll * 100.0)
    assert near["annualized_roll_yield_pct"] == pytest.approx(
        expected_roll * (365.0 / 60.0) * 100.0
    )
    assert far["roll_yield"] is None

    spreads = result["calendar_spreads"]
    assert len(spreads) == 1
    spread = spreads[0]
    assert spread["near_symbol"] == "NEAR"
    assert spread["far_symbol"] == "FAR"
    assert spread["near_price"] == pytest.approx(102.0)
    assert spread["far_price"] == pytest.approx(106.0)
    assert spread["days_between"] == pytest.approx(60.0)
    assert spread["spread"] == pytest.approx(4.0)
    assert spread["spread_pct"] == pytest.approx((4.0 / 102.0) * 100.0)
    assert spread["annualized_spread_pct"] == pytest.approx(
        (4.0 / 102.0) * (365.0 / 60.0) * 100.0
    )
    assert spread["state"] == "contango"

    assert result["front_roll_yield"] == pytest.approx(expected_roll)
    assert result["front_roll_yield_pct"] == pytest.approx(expected_roll * 100.0)
    assert result["next_contract_symbol"] == "FAR"


def test_backwardation_roll_yield_is_positive_for_long_near():
    result = analyze_futures_curve(
        100.0,
        [
            _contract("NEAR", 30.0, 102.0),
            _contract("FAR", 90.0, 98.0),
        ],
    )
    near = result["contracts"][0]
    assert near["roll_yield"] == pytest.approx((102.0 - 98.0) / 98.0)
    assert near["roll_yield"] > 0
    assert result["calendar_spreads"][0]["state"] == "backwardation"


def test_expired_or_invalid_contracts_do_not_create_spreads():
    result = analyze_futures_curve(
        100.0,
        [
            _contract("EXPIRED", 0.0, 101.0),
            _contract("NEAR", 30.0, 102.0),
            {"contract_symbol": "BAD", "days_to_expiry": 60.0},
        ],
    )
    assert result["calendar_spreads"] == []
    assert result["front_roll_yield"] is None
    assert result["next_contract_symbol"] is None


def test_single_contract_has_no_calendar_spread():
    result = analyze_futures_curve(100.0, [_contract("ONLY", 30.0, 102.0)])
    assert result["calendar_spreads"] == []
    assert result["contracts"][0]["roll_yield"] is None
    assert result["front_roll_yield"] is None
