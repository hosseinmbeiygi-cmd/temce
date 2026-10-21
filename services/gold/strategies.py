"""Option strategy builder math for gold derivatives.

Every strategy is represented as signed legs:

* long option / underlying: positive quantity
* short option: negative quantity
* ``premium`` is per option unit and is paid by a long leg / received by a
  short leg
* an underlying leg carries ``entry_price`` and settles at the underlying price

``net_debit`` is positive for a debit and negative for a credit.  Expiry P&L is
terminal cash flow minus the net debit.  Pre-expiry value is the sum of
Black-76 leg values minus the net debit.
"""

from __future__ import annotations

import math
from typing import Any

from services.gold.black76_engine import black76_price

DAYS_PER_YEAR = 365.0
_OPTION_TYPES = ("call", "put")
_TOLERANCE = 1e-9


def _as_float(name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number, got {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number, got {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return number


def _option_type(value: Any) -> str:
    normalized = str(value).strip().lower() if value is not None else ""
    if normalized not in _OPTION_TYPES:
        raise ValueError(f"option_type must be 'call' or 'put', got {value!r}")
    return normalized


def _normalize_leg(leg: dict[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(leg, dict):
        raise ValueError(f"leg {index} must be a mapping")

    asset_type = leg.get("asset_type")
    if asset_type is None:
        asset_type = "option" if leg.get("option_type") is not None else None
        if asset_type is None and "entry_price" in leg:
            asset_type = "underlying"
    if asset_type not in ("option", "underlying"):
        raise ValueError(
            f"leg {index} must have asset_type 'option' or 'underlying'"
        )

    quantity = _as_float(f"leg {index} quantity", leg.get("quantity", 1.0))
    if quantity == 0:
        raise ValueError(f"leg {index} quantity must be non-zero")

    if asset_type == "underlying":
        entry_price = _as_float(
            f"leg {index} entry_price", leg.get("entry_price")
        )
        if entry_price <= 0:
            raise ValueError(f"leg {index} entry_price must be positive")
        return {
            "asset_type": "underlying",
            "quantity": quantity,
            "entry_price": entry_price,
        }

    option_type = _option_type(leg.get("option_type"))
    strike = _as_float(f"leg {index} strike", leg.get("strike"))
    if strike <= 0:
        raise ValueError(f"leg {index} strike must be positive")
    premium = _as_float(f"leg {index} premium", leg.get("premium", 0.0))
    if premium < 0:
        raise ValueError(f"leg {index} premium must be non-negative")

    normalized: dict[str, Any] = {
        "asset_type": "option",
        "option_type": option_type,
        "strike": strike,
        "quantity": quantity,
        "premium": premium,
    }
    if leg.get("iv") is not None:
        iv = _as_float(f"leg {index} iv", leg["iv"])
        if iv <= 0:
            raise ValueError(f"leg {index} iv must be positive")
        normalized["iv"] = iv
    return normalized


def _normalize_legs(legs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not legs:
        raise ValueError("legs must not be empty")
    return [_normalize_leg(leg, index) for index, leg in enumerate(legs)]


def _net_debit(legs: list[dict[str, Any]]) -> float:
    total = 0.0
    for leg in legs:
        if leg["asset_type"] == "underlying":
            total += leg["quantity"] * leg["entry_price"]
        else:
            total += leg["quantity"] * leg["premium"]
    return total


def _payoff_at(price: float, legs: list[dict[str, Any]]) -> float:
    total = 0.0
    for leg in legs:
        quantity = leg["quantity"]
        if leg["asset_type"] == "underlying":
            total += quantity * price
        elif leg["option_type"] == "call":
            total += quantity * max(0.0, price - leg["strike"])
        else:
            total += quantity * max(0.0, leg["strike"] - price)
    return total


def _critical_prices(legs: list[dict[str, Any]], net_debit: float) -> list[float]:
    strikes = sorted(
        {leg["strike"] for leg in legs if leg["asset_type"] == "option"}
    )
    highest = strikes[-1] if strikes else 1.0
    upper = highest * 2.0 + abs(net_debit) + 1.0
    return sorted({0.0, *strikes, upper})


def _breakevens(legs: list[dict[str, Any]], net_debit: float) -> list[float]:
    points = _critical_prices(legs, net_debit)
    values = [_payoff_at(price, legs) - net_debit for price in points]
    roots: list[float] = []

    for price, value in zip(points, values, strict=True):
        if abs(value) <= _TOLERANCE:
            roots.append(price)

    for index in range(len(points) - 1):
        left_price, right_price = points[index], points[index + 1]
        left_value, right_value = values[index], values[index + 1]
        if left_value * right_value < 0.0:
            root = left_price - left_value * (right_price - left_price) / (
                right_value - left_value
            )
            roots.append(root)

    unique: list[float] = []
    for root in sorted(roots):
        if root < -_TOLERANCE:
            continue
        root = max(0.0, root)
        if not unique or abs(root - unique[-1]) > 1e-7:
            unique.append(root)
    return unique


def _extrema(
    legs: list[dict[str, Any]], net_debit: float
) -> tuple[float | None, float | None, bool, bool]:
    points = _critical_prices(legs, net_debit)
    values = [_payoff_at(price, legs) - net_debit for price in points]

    lower_slope = sum(
        -leg["quantity"] for leg in legs if leg["asset_type"] == "option" and leg["option_type"] == "put"
    ) + sum(leg["quantity"] for leg in legs if leg["asset_type"] == "underlying")
    upper_slope = sum(
        leg["quantity"] for leg in legs if leg["asset_type"] == "option" and leg["option_type"] == "call"
    ) + sum(leg["quantity"] for leg in legs if leg["asset_type"] == "underlying")
    del lower_slope  # F >= 0, so the lower tail is bounded by the F=0 point.

    max_profit_unbounded = upper_slope > _TOLERANCE
    max_loss_unbounded = upper_slope < -_TOLERANCE
    max_profit = None if max_profit_unbounded else max(values)
    max_loss = None if max_loss_unbounded else max(0.0, -min(values))
    return max_profit, max_loss, max_profit_unbounded, max_loss_unbounded


def _pre_expiry_value(
    legs: list[dict[str, Any]],
    *,
    net_debit: float,
    pre_expiry_days: float | None,
    pre_expiry_forward: float | None,
    risk_free_rate: float,
) -> tuple[float | None, float | None, str | None]:
    if pre_expiry_days is None or pre_expiry_forward is None:
        return None, None, "pre_expiry_days and pre_expiry_forward are required"
    days = _as_float("pre_expiry_days", pre_expiry_days)
    forward = _as_float("pre_expiry_forward", pre_expiry_forward)
    if days <= 0:
        return None, None, "pre_expiry_days must be positive"
    if forward <= 0:
        return None, None, "pre_expiry_forward must be positive"

    value = 0.0
    for leg in legs:
        if leg["asset_type"] == "underlying":
            value += leg["quantity"] * forward
            continue
        if leg.get("iv") is None:
            return None, None, "iv required for pre-expiry valuation"
        value += leg["quantity"] * black76_price(
            forward,
            leg["strike"],
            days / DAYS_PER_YEAR,
            risk_free_rate,
            leg["iv"],
            leg["option_type"],
        )
    return value, value - net_debit, None


def analyze_strategy(
    legs: list[dict[str, Any]],
    *,
    expiry_price: float | None = None,
    forward_price: float | None = None,
    risk_free_rate: float = 0.0,
    days_to_expiry: float | None = None,
    pre_expiry_days: float | None = None,
    pre_expiry_forward: float | None = None,
) -> dict[str, Any]:
    """Analyze a signed leg set at expiry and, optionally, before expiry."""
    normalized = _normalize_legs(legs)
    rate = _as_float("risk_free_rate", risk_free_rate)
    if rate < 0:
        raise ValueError("risk_free_rate must be non-negative")
    net_debit = _net_debit(normalized)

    expiry_payoff: float | None = None
    expiry_pnl: float | None = None
    if expiry_price is not None:
        price = _as_float("expiry_price", expiry_price)
        if price < 0:
            raise ValueError("expiry_price must be non-negative")
        expiry_payoff = _payoff_at(price, normalized)
        expiry_pnl = expiry_payoff - net_debit

    max_profit, max_loss, profit_unbounded, loss_unbounded = _extrema(
        normalized, net_debit
    )
    pre_value, pre_pnl, pre_error = _pre_expiry_value(
        normalized,
        net_debit=net_debit,
        pre_expiry_days=pre_expiry_days,
        pre_expiry_forward=pre_expiry_forward,
        risk_free_rate=rate,
    )

    return {
        "legs": normalized,
        "net_debit": net_debit,
        "net_credit": -net_debit if net_debit < 0 else 0.0,
        "expiry_price": expiry_price,
        "expiry_payoff": expiry_payoff,
        "expiry_pnl": expiry_pnl,
        "forward_price": forward_price,
        "risk_free_rate": rate,
        "days_to_expiry": days_to_expiry,
        "breakevens": _breakevens(normalized, net_debit),
        "max_profit": max_profit,
        "max_loss": max_loss,
        "max_profit_unbounded": profit_unbounded,
        "max_loss_unbounded": loss_unbounded,
        "pre_expiry_value": pre_value,
        "pre_expiry_pnl": pre_pnl,
        "pre_expiry_error": pre_error,
    }


def straddle_legs(
    strike: float, call_premium: float, put_premium: float, *, quantity: float = 1.0
) -> list[dict[str, Any]]:
    return [
        {
            "option_type": "call",
            "strike": strike,
            "quantity": quantity,
            "premium": call_premium,
        },
        {
            "option_type": "put",
            "strike": strike,
            "quantity": quantity,
            "premium": put_premium,
        },
    ]


def build_straddle(
    strike: float,
    call_premium: float,
    put_premium: float,
    *,
    call_iv: float | None = None,
    put_iv: float | None = None,
    quantity: float = 1.0,
    **analysis_kwargs: Any,
) -> dict[str, Any]:
    legs = straddle_legs(strike, call_premium, put_premium, quantity=quantity)
    if call_iv is not None:
        legs[0]["iv"] = call_iv
    if put_iv is not None:
        legs[1]["iv"] = put_iv
    return analyze_strategy(legs, **analysis_kwargs)


def strangle_legs(
    put_strike: float,
    call_strike: float,
    put_premium: float,
    call_premium: float,
    *,
    quantity: float = 1.0,
) -> list[dict[str, Any]]:
    return [
        {
            "option_type": "put",
            "strike": put_strike,
            "quantity": quantity,
            "premium": put_premium,
        },
        {
            "option_type": "call",
            "strike": call_strike,
            "quantity": quantity,
            "premium": call_premium,
        },
    ]


def build_strangle(
    put_strike: float,
    call_strike: float,
    put_premium: float,
    call_premium: float,
    *,
    put_iv: float | None = None,
    call_iv: float | None = None,
    quantity: float = 1.0,
    **analysis_kwargs: Any,
) -> dict[str, Any]:
    legs = strangle_legs(
        put_strike, call_strike, put_premium, call_premium, quantity=quantity
    )
    if put_iv is not None:
        legs[0]["iv"] = put_iv
    if call_iv is not None:
        legs[1]["iv"] = call_iv
    return analyze_strategy(legs, **analysis_kwargs)


def vertical_spread_legs(
    option_type: str,
    long_strike: float,
    short_strike: float,
    long_premium: float,
    short_premium: float,
    *,
    quantity: float = 1.0,
) -> list[dict[str, Any]]:
    normalized = _option_type(option_type)
    return [
        {
            "option_type": normalized,
            "strike": long_strike,
            "quantity": quantity,
            "premium": long_premium,
        },
        {
            "option_type": normalized,
            "strike": short_strike,
            "quantity": -quantity,
            "premium": short_premium,
        },
    ]


def build_vertical_spread(
    option_type: str,
    long_strike: float,
    short_strike: float,
    long_premium: float,
    short_premium: float,
    *,
    long_iv: float | None = None,
    short_iv: float | None = None,
    quantity: float = 1.0,
    **analysis_kwargs: Any,
) -> dict[str, Any]:
    legs = vertical_spread_legs(
        option_type,
        long_strike,
        short_strike,
        long_premium,
        short_premium,
        quantity=quantity,
    )
    if long_iv is not None:
        legs[0]["iv"] = long_iv
    if short_iv is not None:
        legs[1]["iv"] = short_iv
    return analyze_strategy(legs, **analysis_kwargs)


def iron_condor_legs(
    long_put_strike: float,
    short_put_strike: float,
    short_call_strike: float,
    long_call_strike: float,
    long_put_premium: float,
    short_put_premium: float,
    short_call_premium: float,
    long_call_premium: float,
    *,
    quantity: float = 1.0,
) -> list[dict[str, Any]]:
    return [
        {
            "option_type": "put",
            "strike": long_put_strike,
            "quantity": quantity,
            "premium": long_put_premium,
        },
        {
            "option_type": "put",
            "strike": short_put_strike,
            "quantity": -quantity,
            "premium": short_put_premium,
        },
        {
            "option_type": "call",
            "strike": short_call_strike,
            "quantity": -quantity,
            "premium": short_call_premium,
        },
        {
            "option_type": "call",
            "strike": long_call_strike,
            "quantity": quantity,
            "premium": long_call_premium,
        },
    ]


def build_iron_condor(
    long_put_strike: float,
    short_put_strike: float,
    short_call_strike: float,
    long_call_strike: float,
    long_put_premium: float,
    short_put_premium: float,
    short_call_premium: float,
    long_call_premium: float,
    *,
    long_put_iv: float | None = None,
    short_put_iv: float | None = None,
    short_call_iv: float | None = None,
    long_call_iv: float | None = None,
    quantity: float = 1.0,
    **analysis_kwargs: Any,
) -> dict[str, Any]:
    legs = iron_condor_legs(
        long_put_strike,
        short_put_strike,
        short_call_strike,
        long_call_strike,
        long_put_premium,
        short_put_premium,
        short_call_premium,
        long_call_premium,
        quantity=quantity,
    )
    for leg, iv in zip(
        legs,
        (long_put_iv, short_put_iv, short_call_iv, long_call_iv),
        strict=True,
    ):
        if iv is not None:
            leg["iv"] = iv
    return analyze_strategy(legs, **analysis_kwargs)


def covered_call_legs(
    underlying_entry_price: float,
    call_strike: float,
    call_premium: float,
    *,
    quantity: float = 1.0,
) -> list[dict[str, Any]]:
    return [
        {
            "asset_type": "underlying",
            "quantity": quantity,
            "entry_price": underlying_entry_price,
        },
        {
            "option_type": "call",
            "strike": call_strike,
            "quantity": -quantity,
            "premium": call_premium,
        },
    ]


def build_covered_call(
    underlying_entry_price: float,
    call_strike: float,
    call_premium: float,
    *,
    call_iv: float | None = None,
    quantity: float = 1.0,
    **analysis_kwargs: Any,
) -> dict[str, Any]:
    legs = covered_call_legs(
        underlying_entry_price, call_strike, call_premium, quantity=quantity
    )
    if call_iv is not None:
        legs[1]["iv"] = call_iv
    return analyze_strategy(legs, **analysis_kwargs)


__all__ = [
    "analyze_strategy",
    "build_covered_call",
    "build_iron_condor",
    "build_straddle",
    "build_strangle",
    "build_vertical_spread",
    "covered_call_legs",
    "iron_condor_legs",
    "straddle_legs",
    "strangle_legs",
    "vertical_spread_legs",
]
