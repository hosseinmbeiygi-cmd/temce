"""ISSUE-101: covered-call detection must not confuse shares with contracts.

A STOCK leg's ``quantity`` is a share count; an option leg's ``quantity`` is a
contract count multiplied by ``contract_size`` shares. The old comparison
multiplied the stock count by the option multiplier as well, so 1,000 shares
"covered" 10 short calls (10,000 shares) and the endpoint reported a zero
initial margin for an effectively naked position.
"""

from __future__ import annotations

import pytest

from domain.options.margin_engine import (
    Direction,
    LegType,
    OptionLeg,
    UniversalMarginEngine,
)


def _stock(shares: int, contract_size: int = 1000) -> OptionLeg:
    return OptionLeg(
        leg_type=LegType.STOCK,
        direction=Direction.LONG,
        underlying_price=10_000.0,
        quantity=shares,
        contract_size=contract_size,
    )


def _short_call(contracts: int, contract_size: int = 1000) -> OptionLeg:
    return OptionLeg(
        leg_type=LegType.CALL,
        direction=Direction.SHORT,
        strike=10_500.0,
        premium=5.0,
        underlying_price=10_000.0,
        days_to_expiry=30,
        implied_volatility=0.3,
        quantity=contracts,
        contract_size=contract_size,
    )


def test_undercovered_position_is_not_a_covered_call() -> None:
    """Acceptance: 1,000 shares + 10 short calls → not covered, margin > 0."""
    result = UniversalMarginEngine().calculate_margin([_stock(1_000), _short_call(10)])

    assert result.strategy_type != "covered_call"
    assert result.total_initial_margin > 0


def test_fully_covered_position_is_a_covered_call() -> None:
    """Acceptance: 10,000 shares + 10 short calls → covered, margin 0."""
    result = UniversalMarginEngine().calculate_margin([_stock(10_000), _short_call(10)])

    assert result.strategy_type == "covered_call"
    assert result.total_initial_margin == 0.0
    assert result.total_maintenance_margin == 0.0


def test_coverage_boundary_is_exact() -> None:
    """One share short of full coverage still requires margin."""
    covered = UniversalMarginEngine().calculate_margin([_stock(1_000), _short_call(1)])
    under = UniversalMarginEngine().calculate_margin([_stock(999), _short_call(1)])

    assert covered.strategy_type == "covered_call"
    assert under.strategy_type != "covered_call"


def test_stock_contract_size_is_ignored() -> None:
    """A stock leg's contract_size must not change coverage."""
    with_default = UniversalMarginEngine().calculate_margin([_stock(1_000, 1000), _short_call(1)])
    with_one = UniversalMarginEngine().calculate_margin([_stock(1_000, 1), _short_call(1)])

    assert with_default.strategy_type == with_one.strategy_type == "covered_call"
    assert with_default.total_initial_margin == with_one.total_initial_margin == 0.0


def test_coverage_sums_mixed_contract_sizes() -> None:
    """2×1,000-share calls + 1×500-share call need 2,500 shares."""
    calls = [_short_call(2, 1000), _short_call(1, 500)]

    covered = UniversalMarginEngine().calculate_margin([_stock(2_500)] + calls)
    under = UniversalMarginEngine().calculate_margin([_stock(2_499)] + calls)

    assert covered.strategy_type == "covered_call"
    assert under.strategy_type != "covered_call"


def test_net_premium_ignores_stock_leg_premium() -> None:
    """Share quantity must never be multiplied by the contract multiplier."""
    stock = _stock(1_000)
    stock.premium = 10_000.0  # per-share price someone may pass by mistake
    call = _short_call(1)

    result = UniversalMarginEngine().calculate_margin([stock, call])

    # Only the short call's premium (5 × 1 × 1,000), short = -1.
    assert result.net_premium_flow == pytest.approx(-5_000.0)
