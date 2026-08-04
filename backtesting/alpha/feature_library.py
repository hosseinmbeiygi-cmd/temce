from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np


class FeatureLibrary:
    """Library of microstructure features for alpha generation.

    Each feature is a function that can be computed from market state.
    """

    @staticmethod
    def mid_price(bid: float, ask: float) -> float:
        return (bid + ask) / 2 if bid > 0 and ask > 0 else 0.0

    @staticmethod
    def spread(bid: float, ask: float) -> float:
        return ask - bid if bid > 0 and ask > 0 else 0.0

    @staticmethod
    def spread_pct(bid: float, ask: float) -> float:
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0.0
        return (ask - bid) / mid if mid > 0 else 0.0

    @staticmethod
    def queue_imbalance(bid_vol: float, ask_vol: float) -> float:
        total = bid_vol + ask_vol
        return (bid_vol - ask_vol) / total if total > 0 else 0.0

    @staticmethod
    def order_flow_imbalance(bid_vol: float, ask_vol: float) -> float:
        return FeatureLibrary.queue_imbalance(bid_vol, ask_vol)

    @staticmethod
    def microprice(bid: float, ask: float, bid_vol: float, ask_vol: float) -> float:
        total = bid_vol + ask_vol
        if total == 0:
            return (bid + ask) / 2 if bid > 0 and ask > 0 else 0.0
        return (bid * ask_vol + ask * bid_vol) / total

    @staticmethod
    def signed_volume(price: float, volume: float, side: str) -> float:
        return volume if side == "buy" else -volume

    @staticmethod
    def depth_ratio(bid_vol: float, ask_vol: float) -> float:
        return bid_vol / max(ask_vol, 1)

    @staticmethod
    def log_return(price: float, prev_price: float) -> float:
        if prev_price > 0 and price > 0:
            return np.log(price / prev_price)
        return 0.0


class RollingFeature:
    """A feature computed over a rolling window."""

    def __init__(self, name: str, window: int = 10) -> None:
        self.name = name
        self.window = window
        self._values: deque[float] = deque(maxlen=window)

    def update(self, value: float) -> float:
        self._values.append(value)
        return self.compute()

    def compute(self) -> float:
        if not self._values:
            return 0.0
        return float(np.mean(self._values))

    @property
    def std(self) -> float:
        if len(self._values) < 2:
            return 0.0
        return float(np.std(self._values))

    @property
    def zscore(self) -> float:
        if self.std <= 0 or not self._values:
            return 0.0
        return (self._values[-1] - self.compute()) / self.std

    def reset(self) -> None:
        self._values.clear()


class FeatureSet:
    """A collection of rolling features computed from market state."""

    def __init__(self) -> None:
        self.features: dict[str, RollingFeature] = {}
        self._current_values: dict[str, float] = {}

    def add_feature(self, name: str, window: int = 10) -> None:
        self.features[name] = RollingFeature(name, window)

    def add_default_features(self) -> None:
        windows = {
            "spread": 10,
            "queue_imbalance": 10,
            "microprice": 10,
            "realized_vol": 20,
            "depth_ratio": 10,
            "trade_intensity": 50,
        }
        for name, window in windows.items():
            self.add_feature(name, window)

    def update(self, market_state: dict[str, Any]) -> dict[str, float]:
        bid = market_state.get("best_bid", 0.0)
        ask = market_state.get("best_ask", 0.0)
        bid_vol = market_state.get("bid_volume", 0)
        ask_vol = market_state.get("ask_volume", 0)
        market_state.get("last_price", 0)

        computed: dict[str, float] = {}

        if "spread" in self.features:
            computed["spread"] = self.features["spread"].update(FeatureLibrary.spread_pct(bid, ask))

        if "queue_imbalance" in self.features:
            computed["queue_imbalance"] = self.features["queue_imbalance"].update(FeatureLibrary.queue_imbalance(bid_vol, ask_vol))

        if "microprice" in self.features:
            computed["microprice"] = self.features["microprice"].update(FeatureLibrary.microprice(bid, ask, bid_vol, ask_vol))

        if "depth_ratio" in self.features:
            computed["depth_ratio"] = self.features["depth_ratio"].update(FeatureLibrary.depth_ratio(bid_vol, ask_vol))

        self._current_values = computed
        return computed

    def get_zscore(self, name: str) -> float:
        if name in self.features:
            return self.features[name].zscore
        return 0.0

    def get_values(self) -> dict[str, float]:
        return dict(self._current_values)

    def reset(self) -> None:
        for f in self.features.values():
            f.reset()
        self._current_values.clear()
