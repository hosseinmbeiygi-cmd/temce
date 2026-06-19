from __future__ import annotations

from typing import Any

import numpy as np


def calibrate_impact(
    trade_sizes: list[float],
    price_moves: list[float],
    adv: float,
) -> tuple[float, float]:
    """Calibrate market impact parameters using the square-root law.

    ΔP = η * (Q / ADV)^α

    Uses log-log regression:
    log(ΔP) = log(η) + α * log(Q / ADV)

    Args:
        trade_sizes: List of trade sizes
        price_moves: List of corresponding price moves (absolute returns)
        adv: Average Daily Volume

    Returns:
        Tuple of (eta, alpha) impact parameters
    """
    if len(trade_sizes) < 5 or len(price_moves) < 5:
        return 0.1, 0.6

    x = np.array([max(s / max(adv, 1), 1e-10) for s in trade_sizes])
    y = np.array([max(abs(m), 1e-10) for m in price_moves])

    log_x = np.log(x)
    log_y = np.log(y)

    valid = np.isfinite(log_x) & np.isfinite(log_y)
    log_x = log_x[valid]
    log_y = log_y[valid]

    if len(log_x) < 5:
        return 0.1, 0.6

    coeffs = np.polyfit(log_x, log_y, 1)
    alpha = float(np.clip(coeffs[0], 0.1, 1.5))
    eta = float(np.clip(np.exp(coeffs[1]), 0.001, 1.0))

    return eta, alpha


def estimate_spread_pct(quotes: list[dict[str, Any]]) -> float:
    """Estimate average spread as percentage of mid price."""
    spreads: list[float] = []
    for q in quotes:
        bid = q.get("bid", 0) or q.get("bid_price", 0)
        ask = q.get("ask", 0) or q.get("ask_price", 0)
        if bid > 0 and ask > 0:
            mid = (bid + ask) / 2
            if mid > 0:
                spreads.append((ask - bid) / mid)

    if not spreads:
        return 0.01

    return float(np.mean(spreads))


def estimate_cancel_rate(quotes: list[dict[str, Any]]) -> float:
    """Estimate cancel rate from sequential quote observations."""
    if len(quotes) < 2:
        return 0.12

    total_cancel: float = 0.0
    total_volume: float = 0.0

    for i in range(1, min(len(quotes), 10000)):
        prev = quotes[i - 1]
        curr = quotes[i]
        prev_bid = prev.get("bid_volume", 0) or 0
        curr_bid = curr.get("bid_volume", 0) or 0
        prev_ask = prev.get("ask_volume", 0) or 0
        curr_ask = curr.get("ask_volume", 0) or 0
        trade_vol = curr.get("trade_volume", 0) or 0

        total_cancel += max(0, prev_bid - curr_bid - trade_vol)
        total_cancel += max(0, prev_ask - curr_ask - trade_vol)
        total_volume += prev_bid + prev_ask

    if total_volume <= 0:
        return 0.12

    return total_cancel / total_volume
