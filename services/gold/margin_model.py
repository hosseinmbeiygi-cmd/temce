"""Config-driven margin and stop-out simulation.

The service intentionally contains no exchange margin rates.  Every ratio and
the contract size must come from the caller or from the ``derivatives.margin``
section of ``config/ime_engine_config.yaml``.  Missing configuration is
reported as ``not_configured`` instead of being guessed.

Simulation formulas
-------------------
pnl                    = (price - entry_price) * direction * quantity
                         * contract_size * contract_multiplier
equity                 = starting_equity + pnl
maintenance_requirement = price * contract_size * quantity
                         * contract_multiplier * maintenance_margin_ratio
equity_ratio           = equity / maintenance_requirement

``MARGIN_CALL`` is emitted when ``equity_ratio <= margin_call_equity_ratio``;
``STOP_OUT`` when ``equity_ratio <= stop_out_equity_ratio``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

REQUIRED_MARGIN_KEYS = (
    "initial_margin_ratio",
    "maintenance_margin_ratio",
    "margin_call_equity_ratio",
    "stop_out_equity_ratio",
    "contract_size",
)


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


def _configured_margin_config() -> dict[str, Any]:
    try:
        from core.config.ime_engine import load_ime_config

        return dict(load_ime_config().get("derivatives", {}).get("margin", {}) or {})
    except (ImportError, OSError, TypeError, ValueError) as exc:  # pragma: no cover
        logger.warning("IME margin config unavailable; using defaults: %s", exc)
        return {}


def simulate_margin_path(
    entry_price: float,
    prices: Sequence[float],
    *,
    direction: int = 1,
    quantity: float = 1.0,
    starting_equity: float | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Simulate equity, margin calls and stop-outs over a price path."""
    entry = _as_float("entry_price", entry_price)
    if entry <= 0:
        raise ValueError("entry_price must be positive")
    if direction not in (1, -1):
        raise ValueError(f"direction must be 1 or -1, got {direction!r}")
    qty = _as_float("quantity", quantity)
    if qty <= 0:
        raise ValueError("quantity must be positive")
    if not prices:
        raise ValueError("prices must not be empty")

    price_path = [_as_float("price", price) for price in prices]
    if any(price <= 0 for price in price_path):
        raise ValueError("prices must be positive")

    raw_config = dict(config) if config is not None else _configured_margin_config()
    missing = [key for key in REQUIRED_MARGIN_KEYS if raw_config.get(key) is None]
    if missing:
        return {
            "status": "not_configured",
            "configured": False,
            "missing": missing,
            "config": raw_config,
            "starting_equity": None,
            "initial_margin_requirement": None,
            "steps": [],
            "margin_call": False,
            "margin_call_index": None,
            "stop_out": False,
            "stop_out_index": None,
            "final_equity": None,
        }

    initial_ratio = _as_float(
        "initial_margin_ratio", raw_config["initial_margin_ratio"]
    )
    maintenance_ratio = _as_float(
        "maintenance_margin_ratio", raw_config["maintenance_margin_ratio"]
    )
    margin_call_ratio = _as_float(
        "margin_call_equity_ratio", raw_config["margin_call_equity_ratio"]
    )
    stop_out_ratio = _as_float(
        "stop_out_equity_ratio", raw_config["stop_out_equity_ratio"]
    )
    contract_size = _as_float("contract_size", raw_config["contract_size"])
    multiplier = _as_float(
        "contract_multiplier", raw_config.get("contract_multiplier", 1.0)
    )

    if initial_ratio < 0:
        raise ValueError("initial_margin_ratio must be non-negative")
    if maintenance_ratio < 0:
        raise ValueError("maintenance_margin_ratio must be non-negative")
    if margin_call_ratio < 0:
        raise ValueError("margin_call_equity_ratio must be non-negative")
    if stop_out_ratio < 0:
        raise ValueError("stop_out_equity_ratio must be non-negative")
    if stop_out_ratio > margin_call_ratio:
        raise ValueError("stop_out_equity_ratio must not exceed margin_call_equity_ratio")
    if contract_size <= 0:
        raise ValueError("contract_size must be positive")
    if multiplier <= 0:
        raise ValueError("contract_multiplier must be positive")

    initial_margin = entry * contract_size * qty * multiplier * initial_ratio
    equity_start = (
        _as_float("starting_equity", starting_equity)
        if starting_equity is not None
        else initial_margin
    )
    if equity_start < 0:
        raise ValueError("starting_equity must be non-negative")

    steps: list[dict[str, Any]] = []
    margin_call_index: int | None = None
    stop_out_index: int | None = None

    for index, price in enumerate(price_path):
        pnl = (
            (price - entry)
            * direction
            * qty
            * contract_size
            * multiplier
        )
        equity = equity_start + pnl
        maintenance = (
            price * contract_size * qty * multiplier * maintenance_ratio
        )
        equity_ratio = equity / maintenance if maintenance > 0 else None

        event: str | None = None
        if equity_ratio is not None:
            if equity_ratio <= stop_out_ratio:
                event = "STOP_OUT"
                if stop_out_index is None:
                    stop_out_index = index
            elif equity_ratio <= margin_call_ratio:
                event = "MARGIN_CALL"
                if margin_call_index is None:
                    margin_call_index = index

        steps.append(
            {
                "index": index,
                "price": price,
                "pnl": pnl,
                "equity": equity,
                "maintenance_requirement": maintenance,
                "equity_ratio": equity_ratio,
                "event": event,
            }
        )

    return {
        "status": "ok",
        "configured": True,
        "missing": [],
        "config": {
            "initial_margin_ratio": initial_ratio,
            "maintenance_margin_ratio": maintenance_ratio,
            "margin_call_equity_ratio": margin_call_ratio,
            "stop_out_equity_ratio": stop_out_ratio,
            "contract_size": contract_size,
            "contract_multiplier": multiplier,
        },
        "starting_equity": equity_start,
        "initial_margin_requirement": initial_margin,
        "steps": steps,
        "margin_call": margin_call_index is not None,
        "margin_call_index": margin_call_index,
        "stop_out": stop_out_index is not None,
        "stop_out_index": stop_out_index,
        "final_equity": steps[-1]["equity"],
    }


__all__ = ["REQUIRED_MARGIN_KEYS", "simulate_margin_path"]
