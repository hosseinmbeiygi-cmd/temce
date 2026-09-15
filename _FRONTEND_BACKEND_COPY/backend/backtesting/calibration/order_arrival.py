from __future__ import annotations

from typing import Any


def estimate_arrival_rate(order_timestamps: list[float]) -> float:
    """Estimate order arrival rate as a Poisson process.

    lambda = N_orders / T

    Args:
        order_timestamps: List of timestamps (in seconds)

    Returns:
        Arrival rate (orders per second)
    """
    if len(order_timestamps) < 2:
        return 0.0
    duration = max(order_timestamps[-1] - order_timestamps[0], 1.0)
    return len(order_timestamps) / duration


def estimate_arrival_rate_from_trades(trades: list[dict[str, Any]]) -> float:
    """Estimate arrival rate from trade data.

    Args:
        trades: List of trade dicts with 'timestamp' keys

    Returns:
        Arrival rate (trades per second)
    """
    timestamps = []
    for t in trades:
        ts = t.get("timestamp")
        if ts is not None:
            if hasattr(ts, "timestamp"):
                timestamps.append(ts.timestamp())
            elif isinstance(ts, (int, float)):
                timestamps.append(ts)
    if len(timestamps) < 2:
        return 0.0
    return estimate_arrival_rate(timestamps)


def estimate_trade_intensity(trades: list[dict[str, Any]]) -> float:
    """Estimate trade intensity (trades per second)."""
    return estimate_arrival_rate_from_trades(trades)


def estimate_trade_rate_per_min(trades: list[dict[str, Any]]) -> float:
    """Estimate trade rate in trades per minute."""
    return estimate_arrival_rate_from_trades(trades) * 60.0
