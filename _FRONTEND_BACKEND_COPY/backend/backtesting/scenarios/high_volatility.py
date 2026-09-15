from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class HighVolatilityScenario:
    name: str = "high_volatility"
    base_volatility_pct: float = 0.04
    spike_volatility_pct: float = 0.10
    duration_days: int = 63
    spike_days: int = 5

    def apply(self, prices: list[float]) -> list[float]:
        import numpy as np

        if not prices:
            return []
        last = prices[-1]
        extended = list(prices)
        for day in range(self.duration_days):
            vol = self.spike_volatility_pct if day < self.spike_days else self.base_volatility_pct
            ret = np.random.normal(0, vol)
            last *= 1 + ret
            extended.append(last)
        return extended

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "base_volatility_pct": self.base_volatility_pct,
            "spike_volatility_pct": self.spike_volatility_pct,
            "duration_days": self.duration_days,
        }
