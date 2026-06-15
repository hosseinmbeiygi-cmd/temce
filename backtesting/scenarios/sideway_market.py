from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SidewayMarketScenario:
    name: str = "sideway_market"
    volatility_pct: float = 0.015
    duration_days: int = 252
    mean_reversion_strength: float = 0.1

    def apply(self, prices: list[float]) -> list[float]:
        import numpy as np

        if not prices:
            return []
        last = prices[-1]
        mean_price = np.mean(prices) if prices else last
        extended = list(prices)
        for _ in range(self.duration_days):
            deviation = mean_price - last
            drift = deviation * self.mean_reversion_strength
            shock = np.random.normal(0, self.volatility_pct * last)
            last += drift + shock
            extended.append(last)
        return extended

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "volatility_pct": self.volatility_pct,
            "duration_days": self.duration_days,
        }
