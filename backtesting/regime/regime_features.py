from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np


class MicrostructureFeatures:
    """Computes microstructure features for regime detection from market state."""

    def __init__(self, window: int = 50) -> None:
        self.window = window
        self._spreads: deque[float] = deque(maxlen=window)
        self._imbalances: deque[float] = deque(maxlen=window)
        self._returns: deque[float] = deque(maxlen=window)
        self._trade_intensities: deque[float] = deque(maxlen=window)
        self._bid_volumes: deque[float] = deque(maxlen=window)
        self._ask_volumes: deque[float] = deque(maxlen=window)
        self._last_price: float = 0.0
        self._last_trade_time: float = 0.0
        self._trade_counter: int = 0

    def update(self, market_state: dict[str, Any]) -> dict[str, float]:
        """Update features from latest market state and return current values."""
        bid = market_state.get("best_bid", 0.0)
        ask = market_state.get("best_ask", 0.0)
        bid_vol = market_state.get("bid_volume", 0)
        ask_vol = market_state.get("ask_volume", 0)
        last_price = market_state.get("last_price", 0) or market_state.get("midpoint", 0)
        timestamp = market_state.get("timestamp", 0)

        # Spread
        spread = ask - bid if bid > 0 and ask > 0 else 0.0
        if spread > 0:
            self._spreads.append(spread)

        # Imbalance
        total_vol = bid_vol + ask_vol
        imbalance = (bid_vol - ask_vol) / max(total_vol, 1) if total_vol > 0 else 0.0
        self._imbalances.append(imbalance)

        # Return
        if last_price > 0 and self._last_price > 0:
            ret = (last_price - self._last_price) / self._last_price
            self._returns.append(ret)
        self._last_price = last_price if last_price > 0 else self._last_price

        # Trade intensity (simplified)
        if timestamp != self._last_trade_time:
            self._trade_counter += 1
        if len(self._trade_intensities) == 0 or timestamp != self._last_trade_time:
            self._last_trade_time = timestamp

        # Queue volumes
        if bid_vol > 0:
            self._bid_volumes.append(bid_vol)
        if ask_vol > 0:
            self._ask_volumes.append(ask_vol)

        return self.compute()

    def compute(self) -> dict[str, float]:
        """Compute all current features."""
        features: dict[str, float] = {}

        # Spread features
        if self._spreads:
            features["spread"] = float(np.mean(self._spreads))
            features["spread_std"] = float(np.std(self._spreads))
        else:
            features["spread"] = 0.0
            features["spread_std"] = 0.0

        # Imbalance features
        if self._imbalances:
            features["imbalance"] = float(np.mean(self._imbalances))
            features["abs_imbalance"] = float(np.mean(np.abs(list(self._imbalances))))
        else:
            features["imbalance"] = 0.0
            features["abs_imbalance"] = 0.0

        # Volatility
        if len(self._returns) >= 5:
            features["realized_vol"] = float(np.std(self._returns) * np.sqrt(252 * 60))
            features["volatility_ratio"] = features["realized_vol"] / max(np.mean(list(self._returns)[:5]) + 0.001, 0.001)
        else:
            features["realized_vol"] = 0.0
            features["volatility_ratio"] = 1.0

        # Trade intensity
        features["trade_intensity"] = self._trade_counter / max(len(self._returns), 1)

        # Queue velocity
        bid_mean = float(np.mean(self._bid_volumes)) if self._bid_volumes else 0
        ask_mean = float(np.mean(self._ask_volumes)) if self._ask_volumes else 0
        features["queue_depth_ratio"] = bid_mean / max(ask_mean, 1)

        # Trend strength
        if len(self._returns) >= 10:
            returns_arr = np.array(list(self._returns))
            features["trend_strength"] = float(abs(np.mean(returns_arr)) / max(np.std(returns_arr), 1e-6))
        else:
            features["trend_strength"] = 0.0

        return features

    def reset(self) -> None:
        self._spreads.clear()
        self._imbalances.clear()
        self._returns.clear()
        self._trade_intensities.clear()
        self._bid_volumes.clear()
        self._ask_volumes.clear()
        self._last_price = 0.0
        self._last_trade_time = 0.0
        self._trade_counter = 0
