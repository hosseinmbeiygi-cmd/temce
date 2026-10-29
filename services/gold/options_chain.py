"""Options-chain analytics on top of the Black-76 engine.

The module is deliberately split into two layers:

* :func:`analyze_options_chain` is pure.  It receives plain contract dicts and
  optional historical IV / previous-open-interest data.
* :class:`OptionsChainProvider` is the data seam used by the DB-backed service
  in :mod:`services.gold.options_chain_service`.  Tests use a small fake
  provider and never touch a database or the network.

Formulas
--------
iv_rank        = (iv - min(history)) / (max(history) - min(history)) * 100
iv_percentile  = count(history <= iv) / len(history) * 100
oi_change      = open_interest - previous_open_interest
oi_change_pct  = oi_change / previous_open_interest * 100
skew           = nearest OTM put IV - nearest OTM call IV

An unavailable history or forward price is reported as ``None`` with a reason;
no synthetic values are created.

``iv_rank`` / ``iv_percentile`` are computed only when the history holds at
least ``min_history_days`` observations (STEP 5-FIX-2: N comes from config);
below that both stay ``None`` while ``iv_history_points`` still reports what
exists.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any

from services.gold.black76_engine import calculate_greeks, implied_volatility

DAYS_PER_YEAR = 365.0
DEFAULT_IV_HISTORY_LIMIT = 60

_OPTION_TYPES = ("call", "put")


class OptionsChainProvider(ABC):
    """Abstract data source for a live or mocked option chain."""

    @abstractmethod
    async def load_contracts(
        self, *, commodity: str | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        """Return current option contracts as plain dicts."""

    @abstractmethod
    async def load_forward_price(
        self, *, commodity: str | None, expiry: str | None
    ) -> float | None:
        """Return the matching futures/forward price, or ``None``."""

    @abstractmethod
    async def load_iv_history(
        self, contract_key: str, *, limit: int = DEFAULT_IV_HISTORY_LIMIT
    ) -> list[float]:
        """Return historical IV observations for one contract."""

    @abstractmethod
    async def load_previous_open_interest(
        self, contract_key: str
    ) -> float | None:
        """Return the previous snapshot's open interest, or ``None``."""


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


def _contract_key(contract: dict[str, Any], index: int) -> str:
    for key in ("contract_key", "symbol", "contract_code", "contract_symbol"):
        value = contract.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return f"contract_{index + 1}"


def _expiry_label(contract: dict[str, Any], days: float | None) -> str | None:
    for key in ("expiry", "expiry_date", "date_end", "expiration"):
        value = contract.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    if days is not None:
        return f"{days:g}d"
    return None


def _resolve_days(contract: dict[str, Any], default: float | None) -> float | None:
    raw = contract.get("days_to_expiry", default)
    if raw is None:
        return None
    days = _as_float("days_to_expiry", raw)
    if days < 0:
        raise ValueError(f"days_to_expiry must be non-negative, got {days!r}")
    return days


def _resolve_forward(contract: dict[str, Any], default: float | None) -> float | None:
    raw = contract.get("forward_price", default)
    if raw is None:
        return None
    forward = _as_float("forward_price", raw)
    if forward <= 0:
        raise ValueError(f"forward_price must be positive, got {forward!r}")
    return forward


def _option_type(contract: dict[str, Any]) -> str:
    raw = contract.get("option_type")
    normalized = str(raw).strip().lower() if raw is not None else ""
    if normalized not in _OPTION_TYPES:
        raise ValueError(f"option_type must be 'call' or 'put', got {raw!r}")
    return normalized


def _strike(contract: dict[str, Any]) -> float:
    if "strike" not in contract:
        raise ValueError("contract missing strike")
    strike = _as_float("strike", contract["strike"])
    if strike <= 0:
        raise ValueError(f"strike must be positive, got {strike!r}")
    return strike


def _market_price(contract: dict[str, Any]) -> float:
    if contract.get("market_price") is None:
        raise ValueError("contract missing market_price")
    price = _as_float("market_price", contract["market_price"])
    if price <= 0:
        raise ValueError(f"market_price must be positive, got {price!r}")
    return price


def _history_stats(
    iv: float | None, history: list[float], *, min_days: int = 1
) -> tuple[float | None, float | None, int]:
    points = [float(value) for value in history if value is not None]
    if iv is None or not points:
        return None, None, len(points)
    if len(points) < max(1, min_days):
        # STEP 5-FIX-2: fewer than N stored days — rank/percentile stay null
        # instead of estimating from a thin sample.
        return None, None, len(points)

    percentile = sum(1 for value in points if value <= iv) / len(points) * 100.0
    if len(points) < 2:
        return None, percentile, len(points)

    low = min(points)
    high = max(points)
    if high <= low:
        return None, percentile, len(points)
    rank = (iv - low) / (high - low) * 100.0
    return rank, percentile, len(points)


def _liquidity_reasons(
    contract: dict[str, Any], thresholds: dict[str, float] | None
) -> list[str]:
    if not thresholds:
        return []

    reasons: list[str] = []
    volume = _as_float("volume", contract.get("volume", 0) or 0)
    open_interest = _as_float(
        "open_interest", contract.get("open_interest", 0) or 0
    )

    min_volume = thresholds.get("min_volume")
    if min_volume is not None and volume < float(min_volume):
        reasons.append("volume_below_minimum")

    min_oi = thresholds.get("min_open_interest")
    if min_oi is not None and open_interest < float(min_oi):
        reasons.append("open_interest_below_minimum")

    max_spread = thresholds.get("max_bid_ask_spread_pct")
    if max_spread is not None:
        bid = contract.get("bid", contract.get("bid_price_1"))
        ask = contract.get("ask", contract.get("ask_price_1"))
        try:
            bid_value = _as_float("bid", bid)
            ask_value = _as_float("ask", ask)
        except (TypeError, ValueError):
            reasons.append("missing_bid_ask")
        else:
            if bid_value <= 0 or ask_value <= 0 or ask_value < bid_value:
                reasons.append("missing_bid_ask")
            else:
                mid = (bid_value + ask_value) / 2.0
                spread_pct = (ask_value - bid_value) / mid * 100.0
                if spread_pct > float(max_spread):
                    reasons.append("bid_ask_spread_above_maximum")

    return reasons


def _enrich_contract(
    contract: dict[str, Any],
    index: int,
    *,
    default_forward: float | None,
    default_days: float | None,
    risk_free_rate: float,
    iv_history: list[float],
    previous_open_interest: float | None,
    liquidity_thresholds: dict[str, float] | None,
    min_history_days: int = 1,
) -> dict[str, Any]:
    row = dict(contract)
    key = _contract_key(contract, index)
    row["contract_key"] = key
    row["iv"] = None
    row["iv_error"] = None
    row["iv_rank"] = None
    row["iv_percentile"] = None
    row["iv_history_points"] = 0
    row["oi_change"] = None
    row["oi_change_pct"] = None
    row["is_liquid"] = True
    row["liquidity_reasons"] = []

    try:
        days = _resolve_days(contract, default_days)
        forward = _resolve_forward(contract, default_forward)
        strike = _strike(contract)
        option_type = _option_type(contract)
        market_price = _market_price(contract)
    except (TypeError, ValueError) as exc:
        row["iv_error"] = str(exc)
        row["expiry"] = _expiry_label(contract, None)
        row["days_to_expiry"] = None
        row["forward_price"] = None
        return row

    row["expiry"] = _expiry_label(contract, days)
    row["days_to_expiry"] = days
    row["forward_price"] = forward

    if forward is None:
        row["iv_error"] = "forward_price unavailable"
    elif days is None or days <= 0:
        row["iv_error"] = "days_to_expiry must be positive"
    else:
        try:
            iv = implied_volatility(
                market_price,
                forward,
                strike,
                days / DAYS_PER_YEAR,
                risk_free_rate,
                option_type,
            )
        except (TypeError, ValueError, RuntimeError) as exc:
            row["iv_error"] = str(exc)
        else:
            if iv is None:
                # Audit FIN-04: no arbitrage-free sigma — report it, never a
                # fabricated 0%/absurd IV.
                row["iv_error"] = "implied volatility did not converge"
            else:
                row["iv"] = iv
                row.update(
                    calculate_greeks(
                        forward,
                        strike,
                        days / DAYS_PER_YEAR,
                        risk_free_rate,
                        iv,
                        option_type,
                    )
                )
                rank, percentile, points = _history_stats(
                    iv, iv_history, min_days=min_history_days
                )
                row["iv_rank"] = rank
                row["iv_percentile"] = percentile
                row["iv_history_points"] = points

    current_oi = _as_float("open_interest", contract.get("open_interest", 0) or 0)
    previous = contract.get("previous_open_interest", previous_open_interest)
    if previous is not None:
        previous_value = _as_float("previous_open_interest", previous)
        change = current_oi - previous_value
        row["oi_change"] = change
        row["oi_change_pct"] = (
            change / previous_value * 100.0 if previous_value > 0 else None
        )

    reasons = _liquidity_reasons(contract, liquidity_thresholds)
    row["liquidity_reasons"] = reasons
    row["is_liquid"] = not reasons
    return row


def _group_by_expiry(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        label = row.get("expiry")
        if label is None:
            continue
        groups[str(label)].append(row)
    return groups


def _skew_for_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    forward = next(
        (row["forward_price"] for row in rows if row.get("forward_price") is not None),
        None,
    )
    days = next(
        (row["days_to_expiry"] for row in rows if row.get("days_to_expiry") is not None),
        None,
    )
    payload: dict[str, Any] = {
        "expiry": rows[0].get("expiry") if rows else None,
        "days_to_expiry": days,
        "forward_price": forward,
        "put_strike": None,
        "put_iv": None,
        "call_strike": None,
        "call_iv": None,
        "skew": None,
        "reason": None,
    }
    if forward is None:
        payload["reason"] = "forward_price unavailable"
        return payload

    puts = [
        row
        for row in rows
        if row.get("iv") is not None
        and str(row.get("option_type", "")).strip().lower() == "put"
        and float(row["strike"]) < forward
    ]
    calls = [
        row
        for row in rows
        if row.get("iv") is not None
        and str(row.get("option_type", "")).strip().lower() == "call"
        and float(row["strike"]) > forward
    ]
    if not puts or not calls:
        payload["reason"] = "requires OTM put and OTM call with valid IV"
        return payload

    put = max(puts, key=lambda row: float(row["strike"]))
    call = min(calls, key=lambda row: float(row["strike"]))
    payload.update(
        {
            "put_strike": float(put["strike"]),
            "put_iv": float(put["iv"]),
            "call_strike": float(call["strike"]),
            "call_iv": float(call["iv"]),
            "skew": float(put["iv"]) - float(call["iv"]),
        }
    )
    return payload


def _term_structure(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for group in _group_by_expiry(rows).values():
        forward = next(
            (row["forward_price"] for row in group if row.get("forward_price") is not None),
            None,
        )
        valid = [row for row in group if row.get("iv") is not None]
        if forward is None or not valid:
            continue
        atm = min(valid, key=lambda row: (abs(float(row["strike"]) - forward), float(row["strike"])))
        points.append(
            {
                "expiry": atm.get("expiry"),
                "days_to_expiry": atm.get("days_to_expiry"),
                "forward_price": forward,
                "atm_strike": float(atm["strike"]),
                "atm_iv": float(atm["iv"]),
                "contract_key": atm.get("contract_key"),
            }
        )
    points.sort(key=lambda point: (point["days_to_expiry"] is None, point["days_to_expiry"] or 0.0))
    return points


def analyze_options_chain(
    contracts: list[dict[str, Any]],
    *,
    forward_price: float | None,
    risk_free_rate: float,
    days_to_expiry: float | None,
    iv_history_by_contract: dict[str, list[float]] | None = None,
    previous_open_interest_by_contract: dict[str, float] | None = None,
    liquidity_thresholds: dict[str, float] | None = None,
    min_history_days: int = 1,
) -> dict[str, Any]:
    """Enrich a chain with IV, rank/percentile, skew, term structure and OI."""
    if risk_free_rate is None or not math.isfinite(float(risk_free_rate)):
        raise ValueError("risk_free_rate must be finite")
    rate = float(risk_free_rate)
    if rate < 0:
        raise ValueError("risk_free_rate must be non-negative")
    if days_to_expiry is not None:
        days_to_expiry = _as_float("days_to_expiry", days_to_expiry)
        if days_to_expiry < 0:
            raise ValueError("days_to_expiry must be non-negative")

    histories = iv_history_by_contract or {}
    previous = previous_open_interest_by_contract or {}
    rows = [
        _enrich_contract(
            contract,
            index,
            default_forward=forward_price,
            default_days=days_to_expiry,
            risk_free_rate=rate,
            iv_history=histories.get(_contract_key(contract, index), []),
            previous_open_interest=previous.get(_contract_key(contract, index)),
            liquidity_thresholds=liquidity_thresholds,
            min_history_days=min_history_days,
        )
        for index, contract in enumerate(contracts)
    ]

    if not rows:
        return {
            "available": False,
            "reason": "no option contracts",
            "forward_price": forward_price,
            "risk_free_rate": rate,
            "contracts": [],
            "contracts_count": 0,
            "skew_by_expiry": [],
            "iv_term_structure": [],
            "iv_available": False,
            "iv_history_available": False,
        }

    groups = _group_by_expiry(rows)
    skew = [
        _skew_for_group(group)
        for _, group in sorted(
            groups.items(),
            key=lambda item: (
                next(
                    (row["days_to_expiry"] for row in item[1] if row.get("days_to_expiry") is not None),
                    None,
                )
                is None,
                next(
                    (row["days_to_expiry"] for row in item[1] if row.get("days_to_expiry") is not None),
                    0.0,
                ),
            ),
        )
    ]

    return {
        "available": True,
        "reason": None,
        "forward_price": forward_price,
        "risk_free_rate": rate,
        "contracts": rows,
        "contracts_count": len(rows),
        "skew_by_expiry": skew,
        "iv_term_structure": _term_structure(rows),
        "iv_available": any(row.get("iv") is not None for row in rows),
        "iv_history_available": any(row.get("iv_history_points", 0) > 0 for row in rows),
        "liquidity_thresholds": dict(liquidity_thresholds or {}),
    }


async def build_options_chain_report(
    provider: OptionsChainProvider,
    *,
    commodity: str | None = None,
    limit: int = 500,
    forward_price: float | None = None,
    risk_free_rate: float = 0.0,
    days_to_expiry: float | None = None,
    iv_history_limit: int = DEFAULT_IV_HISTORY_LIMIT,
    liquidity_thresholds: dict[str, float] | None = None,
    min_history_days: int = 1,
) -> dict[str, Any]:
    """Load a chain through ``provider`` and run the pure analyzer."""
    contracts = await provider.load_contracts(commodity=commodity, limit=limit)

    forward_cache: dict[str | None, float | None] = {}
    history_cache: dict[str, list[float]] = {}
    previous_cache: dict[str, float | None] = {}
    prepared: list[dict[str, Any]] = []

    for index, contract in enumerate(contracts):
        row = dict(contract)
        key = _contract_key(row, index)
        row["contract_key"] = key
        expiry = row.get("expiry")
        expiry_key = str(expiry) if expiry is not None else None
        if row.get("forward_price") is None:
            if forward_price is not None:
                row["forward_price"] = forward_price
            else:
                if expiry_key not in forward_cache:
                    forward_cache[expiry_key] = await provider.load_forward_price(
                        commodity=commodity, expiry=expiry_key
                    )
                row["forward_price"] = forward_cache[expiry_key]
        if key not in history_cache:
            history_cache[key] = await provider.load_iv_history(
                key, limit=iv_history_limit
            )
        if row.get("previous_open_interest") is None:
            if key not in previous_cache:
                previous_cache[key] = await provider.load_previous_open_interest(key)
            if previous_cache[key] is not None:
                row["previous_open_interest"] = previous_cache[key]
        prepared.append(row)

    report = analyze_options_chain(
        prepared,
        forward_price=forward_price,
        risk_free_rate=risk_free_rate,
        days_to_expiry=days_to_expiry,
        iv_history_by_contract=history_cache,
        previous_open_interest_by_contract={
            key: value for key, value in previous_cache.items() if value is not None
        },
        liquidity_thresholds=liquidity_thresholds,
        min_history_days=min_history_days,
    )
    report["source"] = "provider"
    report["iv_history_source"] = (
        "provider" if report["iv_history_available"] else "unavailable"
    )
    return report


__all__ = [
    "DEFAULT_IV_HISTORY_LIMIT",
    "OptionsChainProvider",
    "analyze_options_chain",
    "build_options_chain_report",
]
