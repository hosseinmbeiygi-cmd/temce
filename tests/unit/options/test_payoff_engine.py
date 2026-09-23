"""Reference-scenario tests for the pure payoff engine (spec §3.1)."""

from __future__ import annotations

import pytest

from domain.options.payoff import (
    OptionLeg,
    build_payoff_curve,
    calculate_payoff_at_price,
    find_break_even_points,
    find_max_profit_loss,
)


def test_long_call_reference() -> None:
    legs = [OptionLeg(type="call", action="buy", strike=100, premium=10, quantity=1)]
    assert calculate_payoff_at_price(legs, 90) == pytest.approx(-10)
    assert calculate_payoff_at_price(legs, 100) == pytest.approx(-10)
    assert calculate_payoff_at_price(legs, 110) == pytest.approx(0)
    assert calculate_payoff_at_price(legs, 130) == pytest.approx(20)
    assert find_break_even_points(legs, 50, 150, 5) == pytest.approx([110])
    extremes = find_max_profit_loss(legs, 50, 150)
    assert extremes["max_loss"] == pytest.approx(-10)
    assert extremes["max_profit"] == pytest.approx(40)
    assert extremes["max_profit_unbounded"] is True
    assert extremes["max_loss_unbounded"] is False


def test_long_put_reference() -> None:
    legs = [OptionLeg(type="put", action="buy", strike=100, premium=10, quantity=1)]
    assert calculate_payoff_at_price(legs, 80) == pytest.approx(10)
    assert calculate_payoff_at_price(legs, 100) == pytest.approx(-10)
    assert calculate_payoff_at_price(legs, 130) == pytest.approx(-10)
    assert calculate_payoff_at_price(legs, 0) == pytest.approx(90)
    assert find_break_even_points(legs, 0, 150, 5) == pytest.approx([90])
    extremes = find_max_profit_loss(legs, 0, 150)
    assert extremes["max_profit"] == pytest.approx(90)
    assert extremes["max_loss"] == pytest.approx(-10)
    assert extremes["max_profit_unbounded"] is False
    assert extremes["max_loss_unbounded"] is False


def test_long_straddle_reference() -> None:
    legs = [
        OptionLeg(type="call", action="buy", strike=100, premium=10, quantity=1),
        OptionLeg(type="put", action="buy", strike=100, premium=10, quantity=1),
    ]
    assert calculate_payoff_at_price(legs, 100) == pytest.approx(-20)
    assert calculate_payoff_at_price(legs, 80) == pytest.approx(0)
    assert calculate_payoff_at_price(legs, 120) == pytest.approx(0)
    assert calculate_payoff_at_price(legs, 130) == pytest.approx(10)
    assert find_break_even_points(legs, 50, 150, 5) == pytest.approx([80, 120])
    extremes = find_max_profit_loss(legs, 0, 200)
    assert extremes["max_loss"] == pytest.approx(-20)
    assert extremes["max_profit_unbounded"] is True
    assert extremes["max_loss_unbounded"] is False


def test_bull_call_spread_reference() -> None:
    legs = [
        OptionLeg(type="call", action="buy", strike=100, premium=7, quantity=1),
        OptionLeg(type="call", action="sell", strike=105, premium=3, quantity=1),
    ]
    assert calculate_payoff_at_price(legs, 95) == pytest.approx(-4)
    assert calculate_payoff_at_price(legs, 100) == pytest.approx(-4)
    assert calculate_payoff_at_price(legs, 104) == pytest.approx(0)
    assert calculate_payoff_at_price(legs, 120) == pytest.approx(1)
    assert find_break_even_points(legs, 50, 150, 5) == pytest.approx([104])
    extremes = find_max_profit_loss(legs, 50, 150)
    assert extremes["max_profit"] == pytest.approx(1)
    assert extremes["max_loss"] == pytest.approx(-4)
    assert extremes["max_profit_unbounded"] is False
    assert extremes["max_loss_unbounded"] is False


def test_covered_call_reference() -> None:
    legs = [
        OptionLeg(type="stock", action="buy", strike=0, premium=100, quantity=100),
        OptionLeg(type="call", action="sell", strike=110, premium=5, quantity=100),
    ]
    assert calculate_payoff_at_price(legs, 90) == pytest.approx(-500)
    assert calculate_payoff_at_price(legs, 110) == pytest.approx(1500)
    assert calculate_payoff_at_price(legs, 130) == pytest.approx(1500)
    assert find_break_even_points(legs, 0, 150, 5) == pytest.approx([95])
    extremes = find_max_profit_loss(legs, 0, 150)
    assert extremes["max_profit"] == pytest.approx(1500)
    assert extremes["max_loss"] == pytest.approx(-9500)
    assert extremes["max_profit_unbounded"] is False
    assert extremes["max_loss_unbounded"] is False


def test_iron_condor_reference() -> None:
    legs = [
        OptionLeg(type="put", action="buy", strike=90, premium=2, quantity=1),
        OptionLeg(type="put", action="sell", strike=95, premium=4, quantity=1),
        OptionLeg(type="call", action="sell", strike=105, premium=4, quantity=1),
        OptionLeg(type="call", action="buy", strike=110, premium=2, quantity=1),
    ]
    assert calculate_payoff_at_price(legs, 100) == pytest.approx(4)
    assert calculate_payoff_at_price(legs, 80) == pytest.approx(-1)
    assert calculate_payoff_at_price(legs, 120) == pytest.approx(-1)
    assert find_break_even_points(legs, 80, 120, 5) == pytest.approx([91, 109])
    extremes = find_max_profit_loss(legs, 80, 120)
    assert extremes["max_profit"] == pytest.approx(4)
    assert extremes["max_loss"] == pytest.approx(-1)
    assert extremes["max_profit_unbounded"] is False
    assert extremes["max_loss_unbounded"] is False


def test_contract_size_multiplier_matches_spec_example() -> None:
    legs = [
        OptionLeg(type="call", action="buy", strike=8000, premium=650, quantity=10),
        OptionLeg(type="call", action="sell", strike=8500, premium=300, quantity=10),
    ]
    assert calculate_payoff_at_price(legs, 6000, contract_size=1000) == pytest.approx(-3_500_000)
    assert calculate_payoff_at_price(legs, 11000, contract_size=1000) == pytest.approx(1_500_000)
    assert find_break_even_points(legs, 6000, 11000, 100, contract_size=1000) == pytest.approx([8350])
    extremes = find_max_profit_loss(legs, 6000, 11000, contract_size=1000)
    assert extremes["max_profit"] == pytest.approx(1_500_000)
    assert extremes["max_loss"] == pytest.approx(-3_500_000)


def test_payoff_curve_grid_and_endpoints() -> None:
    legs = [OptionLeg(type="call", action="buy", strike=100, premium=10, quantity=1)]
    curve = build_payoff_curve(legs, 50, 150, 50)
    assert [point["price"] for point in curve] == pytest.approx([50, 100, 150])
    assert [point["payoff"] for point in curve] == pytest.approx([-10, -10, 40])


def test_invalid_inputs_raise_value_error() -> None:
    legs = [OptionLeg(type="call", action="buy", strike=100, premium=10, quantity=1)]
    with pytest.raises(ValueError):
        OptionLeg(type="call", action="buy", strike=100, premium=-1, quantity=1)
    with pytest.raises(ValueError):
        OptionLeg(type="call", action="buy", strike=100, premium=10, quantity=-1)
    with pytest.raises(ValueError):
        build_payoff_curve(legs, 150, 150, 10)
    with pytest.raises(ValueError):
        build_payoff_curve(legs, 100, 150, 0)
    with pytest.raises(ValueError):
        build_payoff_curve(legs, 100, 150, 10, contract_size=0)
