"""FIN-09/FIN-10: contract size default and diagonal spreads.

* ``OptionLeg.contract_size`` defaulted to 1 while ``entities.Option`` uses
  1,000 shares per contract — any caller that omitted the size got a margin
  three orders of magnitude too small.
* A two-leg option pair with different strikes **and different expiries** is a
  diagonal, not a vertical. It was charged the width-based vertical margin,
  although the legs never cap each other at a single expiry.
"""

from __future__ import annotations

import pytest

from domain.options.entities import DEFAULT_OPTION_CONTRACT_SIZE
from domain.options.margin_engine import (
    DEFAULT_CONFIG,
    Direction,
    LegType,
    OptionLeg,
    UniversalMarginEngine,
)


def _leg(**overrides) -> OptionLeg:
    base = {
        "leg_type": LegType.CALL,
        "direction": Direction.SHORT,
        "strike": 10_000.0,
        "premium": 5.0,
        "underlying_price": 10_000.0,
        "days_to_expiry": 30,
        "quantity": 1,
    }
    base.update(overrides)
    return OptionLeg(**base)


def test_contract_size_default_is_the_exchange_contract() -> None:
    leg = _leg()

    assert leg.contract_size == DEFAULT_OPTION_CONTRACT_SIZE == 1_000

    engine = UniversalMarginEngine()
    margin = engine.calculate_margin([leg]).total_initial_margin
    # single naked short → default branch applies the 20% portfolio discount:
    # (0 + 0.25 * 10,000 + 5) * 1 * 1,000 * (1 - 0.20)
    assert margin == pytest.approx(2_004_000.0)


def test_diagonal_spread_keeps_full_naked_margin() -> None:
    short_leg = _leg(strike=10_000.0, days_to_expiry=30)
    long_leg = _leg(
        direction=Direction.LONG, strike=12_000.0, days_to_expiry=60, premium=2.0
    )

    result = UniversalMarginEngine().calculate_margin([short_leg, long_leg])

    assert result.strategy_type == "diagonal_spread"
    naked = (0.25 * 10_000.0 + 5.0) * 1 * 1_000
    assert result.total_initial_margin == pytest.approx(naked)
    assert result.total_maintenance_margin == pytest.approx(
        naked * DEFAULT_CONFIG["maintenance_ratio"]
    )


def test_same_expiry_pair_is_still_a_vertical_spread() -> None:
    short_leg = _leg(strike=10_000.0, premium=5.0, days_to_expiry=30)
    long_leg = _leg(
        direction=Direction.LONG, strike=12_000.0, premium=2.0, days_to_expiry=30
    )

    result = UniversalMarginEngine().calculate_margin([short_leg, long_leg])

    assert result.strategy_type == "bear_call_spread"
    # width(2,000) * size(1,000) - net_credit(3 * 1,000) = 1,997,000
    assert result.total_initial_margin == pytest.approx(1_997_000.0)
