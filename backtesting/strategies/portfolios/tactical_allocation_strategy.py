from __future__ import annotations

from typing import Any

import numpy as np

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent


class TacticalAllocationStrategy(BaseStrategy):
    def __init__(
        self,
        instrument_ids: list[str] | None = None,
        lookback: int = 60,
        momentum_weight: float = 0.5,
        vol_weight: float = 0.3,
        correlation_weight: float = 0.2,
    ) -> None:
        super().__init__(name="TacticalAllocation")
        self.instrument_ids = instrument_ids or []
        self.lookback = lookback
        self.momentum_weight = momentum_weight
        self.vol_weight = vol_weight
        self.correlation_weight = correlation_weight
        self._price_history: dict[str, list[float]] = {}
        self._weights: dict[str, float] = {}

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        for inst_id in self.instrument_ids:
            price = (
                bar.get("close", 0)
                if isinstance(bar.get("close"), (int, float))
                else bar.get(inst_id, {}).get("close", 0)
            )
            if price > 0:
                self._price_history.setdefault(inst_id, []).append(price)
        if len(self._price_history.get(self.instrument_ids[0], [])) < self.lookback:
            return []
        self._compute_tactical_weights()
        return []

    def _compute_tactical_weights(self) -> None:
        scores: dict[str, float] = {}
        for inst_id in self.instrument_ids:
            prices = self._price_history[inst_id][-self.lookback :]
            returns = np.diff(prices) / prices[:-1]
            momentum = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
            vol = np.std(returns) if len(returns) > 1 else 0.01
            score = (momentum * self.momentum_weight) - (vol * self.vol_weight)
            scores[inst_id] = score
        total_score = sum(scores.values()) or 1.0
        self._weights = {inst: max(0, score / total_score) for inst, score in scores.items()}
        total_w = sum(self._weights.values()) or 1.0
        self._weights = {k: v / total_w for k, v in self._weights.items()}

    def get_weights(self) -> dict[str, float]:
        return dict(self._weights)

    def reset(self) -> None:
        self._price_history.clear()
        self._weights.clear()
