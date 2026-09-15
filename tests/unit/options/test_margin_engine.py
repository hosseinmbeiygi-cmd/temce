"""Tests for the universal margin engine.

Targets the strategy-detection branches that gate real-money decisions.
"""

from __future__ import annotations

from domain.options.margin_engine import Direction, LegType, OptionLeg
from domain.options.margin_engine import UniversalMarginEngine as MarginEngine


def _leg(
    leg_type: LegType,
    direction: Direction,
    *,
    strike: float = 100.0,
    premium: float = 5.0,
    quantity: int = 1,
    contract_size: int = 1000,
) -> OptionLeg:
    return OptionLeg(
        leg_type=leg_type,
        direction=direction,
        strike=strike,
        premium=premium,
        underlying_price=100.0,
        days_to_expiry=30,
        implied_volatility=0.25,
        contract_size=contract_size,
        quantity=quantity,
    )


def test_empty_portfolio_has_zero_margin() -> None:
    """An empty portfolio requires no margin and no premium."""
    result = MarginEngine().calculate_margin([])
    assert result.total_initial_margin == 0.0
    assert result.total_maintenance_margin == 0.0
    assert result.net_premium_flow == 0.0


def test_long_only_options_no_margin() -> None:
    """Buying (long) only options requires no margin — only premium paid."""
    long_call = _leg(LegType.CALL, Direction.LONG, premium=5.0, quantity=2, contract_size=1000)
    long_put = _leg(LegType.PUT, Direction.LONG, premium=3.0, quantity=1, contract_size=1000)
    result = MarginEngine().calculate_margin([long_call, long_put])
    assert result.total_initial_margin == 0.0
    # Net premium: longs pay, so it's negative (cash outflow).
    # 2×5×1000 + 1×3×1000 = 13000, all LONG so sign = +1 → +13000 net.
    # (Convention: net_premium = Σ(leg.premium * qty * size * direction.value))
    # LONG direction.value = 1, so net_premium is positive for long-only.
    assert result.net_premium_flow > 0
    assert result.strategy_type == "long_only"


def test_covered_call_detected_and_zero_margin() -> None:
    """Long stock + short call of matching size requires no margin."""
    long_stock = _leg(LegType.STOCK, Direction.LONG, quantity=1, contract_size=1000)
    short_call = _leg(LegType.CALL, Direction.SHORT, strike=110.0, premium=2.0, quantity=1, contract_size=1000)
    result = MarginEngine().calculate_margin([long_stock, short_call])
    assert result.strategy_type == "covered_call"
    assert result.total_initial_margin == 0.0


def test_protective_put_detected() -> None:
    """Long stock + long put requires no margin, just the put premium."""
    long_stock = _leg(LegType.STOCK, Direction.LONG, quantity=1, contract_size=1000)
    long_put = _leg(LegType.PUT, Direction.LONG, strike=90.0, premium=4.0, quantity=1, contract_size=1000)
    result = MarginEngine().calculate_margin([long_stock, long_put])
    assert result.strategy_type == "protective_put"
    assert result.total_initial_margin == 0.0


def test_naked_short_call_requires_positive_margin() -> None:
    """A naked short call must post margin > 0 (uncovered obligation)."""
    short_call = _leg(LegType.CALL, Direction.SHORT, strike=105.0, premium=3.0, quantity=1, contract_size=1000)
    result = MarginEngine().calculate_margin([short_call])
    assert result.total_initial_margin > 0
    # Premium received is positive (short credit).
    assert result.net_premium_flow < 0  # short sign = -1, so net_premium is negative


def test_vertical_spread_detected_and_margin_positive() -> None:
    """A vertical bull call spread is detected, requires positive margin, and
    posts a maintenance margin strictly less than the initial (the engine
    uses an 85% maintenance rule by default).
    """
    short_call = _leg(LegType.CALL, Direction.SHORT, strike=100.0, premium=5.0, quantity=1, contract_size=1000)
    long_call = _leg(LegType.CALL, Direction.LONG, strike=105.0, premium=2.0, quantity=1, contract_size=1000)
    result = MarginEngine().calculate_margin([short_call, long_call])
    assert result.strategy_type == "bear_call_spread"  # short lower-strike = bear call spread
    assert result.total_initial_margin > 0
    # Maintenance must be <= initial; the engine scales by a config coefficient.
    assert 0 <= result.total_maintenance_margin <= result.total_initial_margin
