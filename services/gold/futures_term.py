"""Futures term-structure analytics for IME gold and coin futures.

Pure functions only: no database, no network and no mutation of the input
contracts.  The module is intentionally independent of the API layer so the
same math can be reused by the Gold Desk snapshot, screeners and tests.

Formulas
--------
basis = futures_price - spot_price

annualized_basis_pct = (basis / spot_price) * (365 / days_to_expiry) * 100

implied_repo_rate = ln(futures_price / spot_price) / (days_to_expiry / 365)

A positive basis (futures above spot) is contango; a negative basis is
backwardation.  Cash-and-carry arbitrage is flagged when the implied
continuously-compounded repo rate exceeds the benchmark yield plus transaction
frictions.

Rates are decimal fractions (``0.30`` means 30%).  ``benchmark_yield`` and
``transaction_frictions`` also accept percentage values (``30.0`` or ``2.0``):
any absolute value greater than 1 is treated as a percentage.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any

DAYS_PER_YEAR: float = 365.0

# Baseline interbank/YTM yield used by the cash-and-carry check.
DEFAULT_BENCHMARK_YIELD: float = 0.30

# Default round-trip frictions for the Iranian market (commission, clearing,
# bid/ask and financing spread).  Callers can override this per call or per
# contract when a more precise estimate is available.
DEFAULT_TRANSACTION_FRICTIONS_PCT: float = 0.01
DEFAULT_TRANSACTION_FRICTIONS: float = DEFAULT_TRANSACTION_FRICTIONS_PCT
TRANSACTION_FRICTIONS: float = DEFAULT_TRANSACTION_FRICTIONS

_PRICE_KEYS = (
    "futures_price",
    "future_price",
    "price",
    "settlement_price",
    "settle",
    "contract_price",
    "close_price",
    "close",
    "last_price",
    "last",
    "market_price",
)

_DAYS_KEYS = (
    "days_to_expiry",
    "days_to_maturity",
    "expiry_days",
    "maturity_days",
    "days",
    "dte",
    "ttm_days",
    "remaining_days",
    "expiry_in_days",
)

_EXPIRY_KEYS = (
    "expiry",
    "expiry_date",
    "expiration",
    "expiration_date",
    "maturity",
    "maturity_date",
    "delivery_date",
    "contract_expiry",
)

_SYMBOL_KEYS = (
    "symbol",
    "contract_symbol",
    "contract_code",
    "ticker",
    "code",
    "name",
    "contract",
)

_FRICTION_KEYS = (
    "transaction_frictions",
    "transaction_friction",
    "transaction_cost",
    "transaction_cost_pct",
    "frictions",
)


def _as_float(name: str, value: Any) -> float:
    """Return a finite float or raise a descriptive ``ValueError``."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number, got {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number, got {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return number


def _normalize_rate(name: str, value: Any) -> float:
    """Normalize a rate to a decimal fraction.

    ``0.30`` and ``"30%"`` both become ``0.30``.  Values with an absolute
    magnitude greater than one are interpreted as percentages.
    """
    if isinstance(value, str) and value.strip().endswith("%"):
        return _as_float(name, value.strip()[:-1]) / 100.0
    rate = _as_float(name, value)
    if abs(rate) > 1.0:
        rate /= 100.0
    return rate


def _coerce_date(name: str, value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        text = text.replace("Z", "+00:00").replace("/", "-")
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            try:
                return datetime.fromisoformat(text).date()
            except ValueError as exc:
                raise ValueError(f"{name} must be an ISO date, got {value!r}") from exc
    raise ValueError(f"{name} must be a date or ISO date string, got {value!r}")


def _resolve_as_of(as_of: date | datetime | str | None) -> date:
    if as_of is None:
        return date.today()
    resolved = _coerce_date("as_of", as_of)
    if resolved is None:
        raise ValueError("as_of must not be empty")
    return resolved


def _resolve_price(contract: Mapping[str, Any]) -> float:
    for key in _PRICE_KEYS:
        if key not in contract or contract[key] is None:
            continue
        raw = contract[key]
        if isinstance(raw, Mapping):
            for nested_key in ("close", "last", "settlement", "price", "value"):
                if nested_key in raw and raw[nested_key] is not None:
                    raw = raw[nested_key]
                    break
        price = _as_float(key, raw)
        if price <= 0:
            raise ValueError(f"{key} must be positive, got {price!r}")
        return price
    raise ValueError("contract has no futures price")


def _resolve_days(
    contract: Mapping[str, Any], as_of: date
) -> tuple[float | None, str | None]:
    """Return ``(days_to_expiry, expiry_iso)`` from either days or a date."""
    for key in _DAYS_KEYS:
        if key not in contract or contract[key] is None:
            continue
        raw = contract[key]
        if isinstance(raw, timedelta):
            return raw.total_seconds() / 86_400.0, None
        if isinstance(raw, str):
            text = raw.strip()
            try:
                return _as_float(key, text), None
            except ValueError:
                parsed = _coerce_date(key, text)
                if parsed is not None:
                    return float((parsed - as_of).days), parsed.isoformat()
                raise
        return _as_float(key, raw), None

    for key in _EXPIRY_KEYS:
        if key not in contract or contract[key] is None:
            continue
        parsed = _coerce_date(key, contract[key])
        if parsed is None:
            continue
        return float((parsed - as_of).days), parsed.isoformat()
    return None, None


def _resolve_symbol(contract: Mapping[str, Any], index: int) -> str:
    for key in _SYMBOL_KEYS:
        value = contract.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return f"contract_{index + 1}"


def _resolve_frictions(contract: Mapping[str, Any], default: float) -> float:
    for key in _FRICTION_KEYS:
        if key in contract and contract[key] is not None:
            return _normalize_rate(key, contract[key])
    return default


def _state_for(futures_price: float, spot_price: float) -> str:
    if futures_price > spot_price:
        return "contango"
    if futures_price < spot_price:
        return "backwardation"
    return "flat"


def _base_contract_result(spot_price: float, symbol: str, index: int) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "contract_symbol": symbol,
        "input_index": index,
        "spot_price": spot_price,
        "futures_price": None,
        "price": None,
        "expiry": None,
        "days_to_expiry": None,
        "days": None,
        "basis": None,
        "basis_pct": None,
        "basis_pct_of_spot": None,
        "annualized_basis": None,
        "annualized_basis_pct": None,
        "implied_repo_rate": None,
        "implied_repo_rate_pct": None,
        "transaction_frictions": None,
        "state": "unavailable",
        "market_state": "UNAVAILABLE",
        "contango": False,
        "backwardation": False,
        "is_flat": False,
        "is_expired": False,
        "term_metrics_available": False,
        "arbitrage": False,
        "carry_arbitrage": False,
        "arbitrage_signal": None,
        "arbitrage_excess": None,
        "arbitrage_excess_pct": None,
        "reverse_arbitrage": False,
        "next_contract_symbol": None,
        "roll_yield": None,
        "roll_yield_pct": None,
        "annualized_roll_yield_pct": None,
        "valid": False,
        "error": None,
        "warning": None,
    }


def _analyze_contract(
    spot_price: float,
    contract: Mapping[str, Any],
    index: int,
    as_of: date,
    benchmark_yield: float,
    default_frictions: float,
) -> dict[str, Any]:
    symbol = _resolve_symbol(contract, index)
    result = _base_contract_result(spot_price, symbol, index)

    try:
        futures_price = _resolve_price(contract)
        days, expiry = _resolve_days(contract, as_of)
    except (TypeError, ValueError) as exc:
        result["error"] = str(exc)
        return result

    result.update(
        {
            "futures_price": futures_price,
            "price": futures_price,
            "expiry": expiry,
            "days_to_expiry": days,
            "days": days,
            "valid": True,
        }
    )

    basis = futures_price - spot_price
    basis_pct = (basis / spot_price) * 100.0
    state = _state_for(futures_price, spot_price)
    result.update(
        {
            "basis": basis,
            "basis_pct": basis_pct,
            "basis_pct_of_spot": basis_pct,
            "state": state,
            "market_state": state.upper(),
            "contango": state == "contango",
            "backwardation": state == "backwardation",
            "is_flat": state == "flat",
        }
    )

    if days is None:
        result["warning"] = "days_to_expiry or expiry date is missing; annualized metrics unavailable"
        return result
    if days <= 0:
        result["is_expired"] = True
        result["warning"] = "contract has expired or expires today; annualized metrics unavailable"
        return result

    annualized_basis = (basis / spot_price) * (DAYS_PER_YEAR / days)
    implied_repo_rate = math.log(futures_price / spot_price) / (days / DAYS_PER_YEAR)
    frictions = _resolve_frictions(contract, default_frictions)
    threshold = benchmark_yield + frictions
    excess = implied_repo_rate - threshold
    reverse_threshold = benchmark_yield - frictions

    result.update(
        {
            "term_metrics_available": True,
            "annualized_basis": annualized_basis,
            "annualized_basis_pct": annualized_basis * 100.0,
            "implied_repo_rate": implied_repo_rate,
            "implied_repo_rate_pct": implied_repo_rate * 100.0,
            "transaction_frictions": frictions,
            "arbitrage": excess > 0.0,
            "carry_arbitrage": excess > 0.0,
            "arbitrage_signal": (
                "CARRY_ARBITRAGE_OPPORTUNITY" if excess > 0.0 else None
            ),
            "arbitrage_excess": excess,
            "arbitrage_excess_pct": excess * 100.0,
            "reverse_arbitrage": implied_repo_rate < reverse_threshold,
        }
    )
    return result


def _sort_key(contract: dict[str, Any]) -> tuple[int, float, int]:
    days = contract.get("days_to_expiry")
    if not contract.get("valid"):
        return (3, 0.0, int(contract["input_index"]))
    if days is None:
        return (2, 0.0, int(contract["input_index"]))
    if days <= 0:
        return (1, float(days), int(contract["input_index"]))
    return (0, float(days), int(contract["input_index"]))


def _curve_state(contracts: list[dict[str, Any]]) -> str:
    valid = [contract for contract in contracts if contract.get("valid")]
    active = [
        contract
        for contract in valid
        if contract.get("days_to_expiry") is not None and contract["days_to_expiry"] > 0
    ]
    candidates = active or valid
    states = {contract["state"] for contract in candidates if contract["state"] != "unavailable"}
    if not states:
        return "unavailable"
    if len(states) == 1:
        return next(iter(states))
    return "mixed"


def analyze_futures_curve(
    spot_price: float,
    contracts: list[dict],
    benchmark_yield: float = DEFAULT_BENCHMARK_YIELD,
    transaction_frictions_pct: float = DEFAULT_TRANSACTION_FRICTIONS_PCT,
    *,
    transaction_frictions: float | None = None,
    as_of: date | datetime | str | None = None,
) -> dict[str, Any]:
    """Analyze a futures curve against spot and an interbank/YTM benchmark.

    Parameters
    ----------
    spot_price:
        Current spot price in the same unit as every contract price.
    contracts:
        Contracts with a price and either ``days_to_expiry`` (or an alias) or
        an expiry date.  Common field aliases are accepted; see the module
        constants.
    benchmark_yield:
        Interbank/YTM benchmark as a decimal fraction (``0.30``) or a
        percentage (``30.0`` or ``"30%"``).
    transaction_frictions_pct:
        Round-trip frictions used in the carry check (``0.01`` means 1%).  A
        contract may override this with ``transaction_frictions``/
        ``transaction_cost``.  ``transaction_frictions=`` is accepted as an
        alias for backward compatibility.
    as_of:
        Reference date for date-based expiries.  Defaults to today.

    Returns
    -------
    dict
        A curve-level summary plus one analyzed entry per contract.  Rates are
        decimals and ``*_pct`` fields are percentages.
    """
    spot = _as_float("spot_price", spot_price)
    if spot <= 0:
        raise ValueError(f"spot_price must be positive, got {spot!r}")
    if not isinstance(contracts, Sequence) or isinstance(contracts, (str, bytes)):
        raise TypeError("contracts must be a sequence of dicts")

    if transaction_frictions is not None:
        transaction_frictions_pct = transaction_frictions

    benchmark = _normalize_rate("benchmark_yield", benchmark_yield)
    frictions = _normalize_rate(
        "transaction_frictions_pct", transaction_frictions_pct
    )
    if frictions < 0:
        raise ValueError(
            f"transaction_frictions_pct must be non-negative, got {frictions!r}"
        )
    resolved_as_of = _resolve_as_of(as_of)

    analyzed: list[dict[str, Any]] = []
    for index, contract in enumerate(contracts):
        if not isinstance(contract, Mapping):
            result = _base_contract_result(spot, f"contract_{index + 1}", index)
            result["error"] = f"contract must be a mapping, got {type(contract).__name__}"
            analyzed.append(result)
            continue
        analyzed.append(
            _analyze_contract(
                spot_price=spot,
                contract=contract,
                index=index,
                as_of=resolved_as_of,
                benchmark_yield=benchmark,
                default_frictions=frictions,
            )
        )

    analyzed.sort(key=_sort_key)
    valid = [contract for contract in analyzed if contract.get("valid")]
    active = [
        contract
        for contract in valid
        if contract.get("days_to_expiry") is not None and contract["days_to_expiry"] > 0
    ]

    calendar_spreads: list[dict[str, Any]] = []
    for near, far in zip(active, active[1:], strict=False):
        days_between = float(far["days_to_expiry"]) - float(near["days_to_expiry"])
        if days_between <= 0:
            continue
        near_price = float(near["futures_price"])
        far_price = float(far["futures_price"])
        spread = far_price - near_price
        spread_pct = spread / near_price * 100.0
        annualized_spread_pct = spread / near_price * (DAYS_PER_YEAR / days_between) * 100.0
        roll_yield = (near_price - far_price) / far_price
        roll_yield_pct = roll_yield * 100.0
        annualized_roll_yield_pct = (
            roll_yield * (DAYS_PER_YEAR / days_between) * 100.0
        )

        near.update(
            {
                "next_contract_symbol": far["symbol"],
                "roll_yield": roll_yield,
                "roll_yield_pct": roll_yield_pct,
                "annualized_roll_yield_pct": annualized_roll_yield_pct,
            }
        )
        calendar_spreads.append(
            {
                "near_symbol": near["symbol"],
                "far_symbol": far["symbol"],
                "near_price": near_price,
                "far_price": far_price,
                "days_between": days_between,
                "spread": spread,
                "spread_pct": spread_pct,
                "annualized_spread_pct": annualized_spread_pct,
                "state": (
                    "contango"
                    if spread > 0
                    else "backwardation"
                    if spread < 0
                    else "flat"
                ),
            }
        )

    front = active[0] if active else (valid[0] if valid else None)

    curve_state = _curve_state(analyzed)
    arbitrage_opportunities = [contract for contract in analyzed if contract.get("arbitrage")]
    reverse_opportunities = [contract for contract in analyzed if contract.get("reverse_arbitrage")]
    best_arbitrage = (
        max(arbitrage_opportunities, key=lambda contract: contract["arbitrage_excess"])
        if arbitrage_opportunities
        else None
    )
    implied_rates = [
        contract["implied_repo_rate"]
        for contract in analyzed
        if contract.get("implied_repo_rate") is not None
    ]

    term_structure = [
        {
            "symbol": contract["symbol"],
            "expiry": contract["expiry"],
            "days_to_expiry": contract["days_to_expiry"],
            "futures_price": contract["futures_price"],
            "basis": contract["basis"],
            "annualized_basis_pct": contract["annualized_basis_pct"],
            "implied_repo_rate": contract["implied_repo_rate"],
            "implied_repo_rate_pct": contract["implied_repo_rate_pct"],
            "state": contract["state"],
        }
        for contract in valid
    ]

    state_label = {
        "contango": "Contango",
        "backwardation": "Backwardation",
        "flat": "Flat",
        "mixed": "Mixed",
        "unavailable": "Unavailable",
    }[curve_state]

    front_basis = front["basis"] if front else None
    front_annualized = front["annualized_basis_pct"] if front else None
    front_implied = front["implied_repo_rate"] if front else None
    front_implied_pct = front["implied_repo_rate_pct"] if front else None

    return {
        "spot_price": spot,
        "as_of": resolved_as_of.isoformat(),
        "benchmark_yield": benchmark,
        "benchmark_yield_pct": benchmark * 100.0,
        "transaction_frictions": frictions,
        "transaction_frictions_pct": frictions * 100.0,
        "arbitrage_threshold": benchmark + frictions,
        "arbitrage_threshold_pct": (benchmark + frictions) * 100.0,
        "threshold_yield": benchmark + frictions,
        "threshold_yield_pct": (benchmark + frictions) * 100.0,
        "n_contracts": len(contracts),
        "curve_state": curve_state,
        "curve_structure": (
            "NO_DATA"
            if not analyzed
            else {
                "contango": "CONTANGO",
                "backwardation": "BACKWARDATION",
                "flat": "FLAT",
                "mixed": "MIXED",
                "unavailable": "UNAVAILABLE",
            }[curve_state]
        ),
        "state": curve_state,
        "state_label": state_label,
        "structure": curve_state,
        "is_contango": curve_state == "contango",
        "is_backwardation": curve_state == "backwardation",
        "is_flat": curve_state == "flat",
        "contango": curve_state == "contango",
        "backwardation": curve_state == "backwardation",
        "front_contract": front,
        "contracts": analyzed,
        "term_structure": term_structure,
        "curve": term_structure,
        "basis": front_basis,
        "annualized_basis_pct": front_annualized,
        "implied_repo_rate": front_implied,
        "implied_repo_rate_pct": front_implied_pct,
        "arbitrage": bool(arbitrage_opportunities),
        "arbitrage_opportunity": bool(arbitrage_opportunities),
        "carry_arbitrage": bool(arbitrage_opportunities),
        "is_carry_arbitrage": bool(arbitrage_opportunities),
        "arbitrage_opportunities": arbitrage_opportunities,
        "opportunities": [
            contract["symbol"] for contract in arbitrage_opportunities
        ],
        "best_arbitrage": best_arbitrage,
        "reverse_arbitrage": bool(reverse_opportunities),
        "reverse_arbitrage_opportunities": reverse_opportunities,
        "max_implied_repo_rate": max(implied_rates) if implied_rates else None,
        "min_implied_repo_rate": min(implied_rates) if implied_rates else None,
        "calendar_spreads": calendar_spreads,
        "front_roll_yield": front.get("roll_yield") if front else None,
        "front_roll_yield_pct": front.get("roll_yield_pct") if front else None,
        "front_annualized_roll_yield_pct": (
            front.get("annualized_roll_yield_pct") if front else None
        ),
        "next_contract_symbol": (
            front.get("next_contract_symbol") if front else None
        ),
        "warnings": [contract["warning"] for contract in analyzed if contract.get("warning")],
    }


__all__ = [
    "DAYS_PER_YEAR",
    "DEFAULT_BENCHMARK_YIELD",
    "DEFAULT_TRANSACTION_FRICTIONS",
    "DEFAULT_TRANSACTION_FRICTIONS_PCT",
    "TRANSACTION_FRICTIONS",
    "analyze_futures_curve",
]
