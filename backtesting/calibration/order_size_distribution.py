from __future__ import annotations

from typing import Any

import numpy as np


def fit_order_size_distribution(sizes: list[float]) -> dict[str, float]:
    """Fit a lognormal distribution to order sizes.

    Args:
        sizes: List of order sizes

    Returns:
        dict with 'mu' and 'sigma' parameters of the lognormal distribution
    """
    if len(sizes) < 3:
        return {"mu": 8.0, "sigma": 1.5}

    log_sizes = np.log([max(s, 1) for s in sizes])
    return {
        "mu": float(np.mean(log_sizes)),
        "sigma": float(np.std(log_sizes)),
    }


def sample_order_size(mu: float, sigma: float, min_size: int = 100, max_size: int = 100_000) -> int:
    """Sample an order size from the fitted distribution.

    Args:
        mu: Mean of log(sizes)
        sigma: Std of log(sizes)
        min_size: Minimum order size
        max_size: Maximum order size

    Returns:
        Sampled order size within bounds
    """
    size = int(np.random.lognormal(mu, sigma))
    return max(min_size, min(size, max_size))


def estimate_avg_trade_size(trades: list[dict[str, Any]]) -> float:
    """Estimate average trade size from trade data.

    Args:
        trades: List of trade dicts with 'volume' or 'quantity' keys

    Returns:
        Average trade size
    """
    volumes = []
    for t in trades:
        vol = t.get("volume") or t.get("quantity", 0)
        if vol > 0:
            volumes.append(float(vol))

    if not volumes:
        return 10_000.0
    return float(np.mean(volumes))


def estimate_adv(trades: list[dict[str, Any]]) -> float:
    """Estimate Average Daily Volume from trade data.

    Args:
        trades: List of trade dicts with 'volume' and 'timestamp' keys

    Returns:
        Estimated ADV
    """
    total_volume = sum(t.get("volume", 0) or t.get("quantity", 0) for t in trades)
    if not trades:
        return 1_000_000.0

    timestamps = []
    for t in trades:
        ts = t.get("timestamp")
        if ts is not None:
            if hasattr(ts, "timestamp"):
                timestamps.append(ts.timestamp())
            elif isinstance(ts, (int, float)):
                timestamps.append(ts)

    if len(timestamps) < 2:
        return float(total_volume)

    span_seconds = max(timestamps[-1] - timestamps[0], 1)
    span_days = span_seconds / (24 * 3600)
    if span_days > 0:
        return total_volume / span_days
    return float(total_volume)
