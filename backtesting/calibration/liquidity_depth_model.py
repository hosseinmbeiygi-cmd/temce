from __future__ import annotations

from typing import Any

import numpy as np


class LiquidityDepthModel:
    """Models order book depth as exponential decay:

    Depth(p) = D0 * exp(-k * |p - mid|)

    where:
    - D0: depth at mid price
    - k: decay coefficient (higher = steeper drop in depth)
    """

    def __init__(self, k: float = 0.001, d0: float = 1_000_000) -> None:
        self.k = k
        self.d0 = d0

    def estimate_depth(self, price: float, mid: float) -> float:
        """Estimate available depth at a given price level."""
        distance = abs(price - mid)
        return self.d0 * np.exp(-self.k * distance)

    def estimate_volume_at_price(self, price: float, mid: float, max_volume: float = 1_000_000) -> int:
        """Estimate available volume at a given price level."""
        depth = self.estimate_depth(price, mid)
        return min(int(depth), max_volume)

    def get_depth_profile(self, mid: float, levels: int = 10, tick_size: float = 0.1) -> dict[str, list[tuple[float, int]]]:
        """Get bid/ask depth profile around the mid price."""
        bids: list[tuple[float, int]] = []
        asks: list[tuple[float, int]] = []
        for i in range(1, levels + 1):
            bid_price = round(mid - i * tick_size, 2)
            ask_price = round(mid + i * tick_size, 2)
            bid_vol = self.estimate_volume_at_price(bid_price, mid)
            ask_vol = self.estimate_volume_at_price(ask_price, mid)
            bids.append((bid_price, bid_vol))
            asks.append((ask_price, ask_vol))
        return {"bids": bids, "asks": asks}

    def calibrate(self, prices: list[float], volumes: list[float], mid: float) -> None:
        """Calibrate k from observed price-volume pairs."""
        if len(prices) < 3:
            return
        distances = [abs(p - mid) for p, v in zip(prices, volumes, strict=False) if v > 0]
        vols = [v for v in volumes if v > 0]
        if len(distances) < 3:
            return
        log_vols = np.log([max(v, 1) for v in vols])
        coeffs = np.polyfit(distances, log_vols, 1)
        self.k = -float(coeffs[0])
        self.d0 = float(np.exp(coeffs[1]))

    def calibrate_from_quotes(self, quotes: list[dict[str, Any]]) -> None:
        """Calibrate from quote data."""
        if len(quotes) < 5:
            return
        bid_prices = [q.get("bid_price", 0) for q in quotes if q.get("bid_price", 0) > 0]
        bid_volumes = [q.get("bid_volume", 0) for q in quotes if q.get("bid_volume", 0) > 0]
        ask_prices = [q.get("ask_price", 0) for q in quotes if q.get("ask_price", 0) > 0]
        ask_volumes = [q.get("ask_volume", 0) for q in quotes if q.get("ask_volume", 0) > 0]

        all_prices = bid_prices + ask_prices
        all_volumes = bid_volumes + ask_volumes

        if len(all_prices) < 5:
            return

        mid = (np.mean(bid_prices) + np.mean(ask_prices)) / 2 if bid_prices and ask_prices else 1000.0
        self.calibrate(all_prices, all_volumes, mid)

    def estimate_queue_lifetime(self, queue_size: int, trade_rate: float, cancel_rate: float) -> float:
        """Estimate how long it takes for a queue position to fill."""
        drain = trade_rate + cancel_rate
        if drain <= 0:
            return float("inf")
        return queue_size / drain

    @property
    def params(self) -> dict[str, float]:
        return {"k": self.k, "d0": self.d0}
