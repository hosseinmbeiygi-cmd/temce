from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LegType = Literal["call", "put", "stock"]
LegAction = Literal["buy", "sell"]

_BISECTION_ITERATIONS = 80
_DEDUP_TOLERANCE = 1e-6
_ZERO_TOLERANCE = 1e-9
_MAX_CURVE_POINTS = 100_000


@dataclass(frozen=True)
class OptionLeg:
    type: LegType
    action: LegAction
    strike: float
    premium: float
    quantity: float = 1.0

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise ValueError("quantity must be non-negative")
        if self.premium < 0:
            raise ValueError("premium must be non-negative")
        if self.type != "stock" and self.strike < 0:
            raise ValueError("strike must be non-negative")


def _validate_range(price_min: float, price_max: float, contract_size: float) -> None:
    if contract_size <= 0:
        raise ValueError("contract_size must be positive")
    if price_min < 0:
        raise ValueError("price_min must be non-negative")
    if price_max <= price_min:
        raise ValueError("price_max must be greater than price_min")


def _validate_inputs(price_min: float, price_max: float, step: float, contract_size: float) -> None:
    _validate_range(price_min, price_max, contract_size)
    if step <= 0:
        raise ValueError("step must be positive")
    if (price_max - price_min) / step > _MAX_CURVE_POINTS:
        raise ValueError(f"price range generates more than {_MAX_CURVE_POINTS} points")


def _unit_payoff_at_expiry(leg: OptionLeg, underlying_price_at_expiry: float) -> float:
    if leg.type == "stock":
        return underlying_price_at_expiry - leg.premium
    if leg.type == "call":
        intrinsic = max(underlying_price_at_expiry - leg.strike, 0.0)
    else:
        intrinsic = max(leg.strike - underlying_price_at_expiry, 0.0)
    return intrinsic - leg.premium


def calculate_payoff_at_price(
    legs: list[OptionLeg],
    underlying_price_at_expiry: float,
    contract_size: float = 1.0,
) -> float:
    total = 0.0
    for leg in legs:
        leg_payoff = _unit_payoff_at_expiry(leg, underlying_price_at_expiry) * leg.quantity
        total += leg_payoff if leg.action == "buy" else -leg_payoff
    return total * contract_size


def _curve_prices(legs: list[OptionLeg], price_min: float, price_max: float, step: float) -> list[float]:
    prices: list[float] = []
    price = price_min
    while price < price_max - _ZERO_TOLERANCE:
        prices.append(price)
        price += step
    prices.append(price_max)
    for leg in legs:
        if leg.type != "stock" and price_min < leg.strike < price_max:
            prices.append(leg.strike)
    return sorted(set(prices))


def build_payoff_curve(
    legs: list[OptionLeg],
    price_min: float,
    price_max: float,
    step: float,
    contract_size: float = 1.0,
) -> list[dict[str, float]]:
    _validate_inputs(price_min, price_max, step, contract_size)
    return [
        {"price": price, "payoff": calculate_payoff_at_price(legs, price, contract_size)}
        for price in _curve_prices(legs, price_min, price_max, step)
    ]


def _bisect_break_even(
    legs: list[OptionLeg],
    low: float,
    high: float,
    contract_size: float,
) -> float:
    payoff_low = calculate_payoff_at_price(legs, low, contract_size)
    for _ in range(_BISECTION_ITERATIONS):
        mid = (low + high) / 2
        payoff_mid = calculate_payoff_at_price(legs, mid, contract_size)
        if payoff_low * payoff_mid <= 0:
            high = mid
        else:
            low = mid
            payoff_low = payoff_mid
    return (low + high) / 2


def _dedupe_points(points: list[float]) -> list[float]:
    result: list[float] = []
    for point in sorted(points):
        if not result or abs(point - result[-1]) > _DEDUP_TOLERANCE * max(1.0, abs(point)):
            result.append(point)
    return result


def find_break_even_points(
    legs: list[OptionLeg],
    price_min: float,
    price_max: float,
    step: float = 1.0,
    contract_size: float = 1.0,
) -> list[float]:
    _validate_inputs(price_min, price_max, step, contract_size)
    prices = _curve_prices(legs, price_min, price_max, step)
    payoffs = [calculate_payoff_at_price(legs, price, contract_size) for price in prices]
    points: list[float] = []
    for index, price in enumerate(prices):
        if abs(payoffs[index]) < _ZERO_TOLERANCE:
            points.append(price)
        if index > 0 and payoffs[index - 1] * payoffs[index] < 0:
            points.append(_bisect_break_even(legs, prices[index - 1], price, contract_size))
    return _dedupe_points(points)


def _unbounded_flags(legs: list[OptionLeg], price_max: float) -> tuple[bool, bool]:
    strikes = [leg.strike for leg in legs if leg.type != "stock"]
    if strikes and price_max < max(strikes):
        return False, False
    slope = 0.0
    for leg in legs:
        unit_slope = 0.0 if leg.type == "put" else 1.0
        slope += (1.0 if leg.action == "buy" else -1.0) * leg.quantity * unit_slope
    return slope > 0, slope < 0


def find_max_profit_loss(
    legs: list[OptionLeg],
    price_min: float,
    price_max: float,
    contract_size: float = 1.0,
) -> dict[str, float | bool]:
    _validate_range(price_min, price_max, contract_size)
    candidates = {price_min, price_max}
    for leg in legs:
        if leg.type != "stock" and price_min <= leg.strike <= price_max:
            candidates.add(leg.strike)
    payoffs = [calculate_payoff_at_price(legs, price, contract_size) for price in sorted(candidates)]
    max_profit_unbounded, max_loss_unbounded = _unbounded_flags(legs, price_max)
    return {
        "max_profit": max(payoffs),
        "max_loss": min(payoffs),
        "max_profit_unbounded": max_profit_unbounded,
        "max_loss_unbounded": max_loss_unbounded,
    }
