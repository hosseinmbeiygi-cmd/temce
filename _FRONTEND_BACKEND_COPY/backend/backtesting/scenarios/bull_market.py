from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BullMarketScenario:
    name: str = "bull_market"
    avg_return_pct: float = 0.15
    volatility_pct: float = 0.02
    duration_days: int = 252

    def apply(self, prices: list[float]) -> list[float]:
        import numpy as np

        if not prices:
            return []
        last = prices[-1]
        extended = list(prices)
        daily_return = self.avg_return_pct / 252
        for _ in range(self.duration_days):
            ret = np.random.normal(daily_return, self.volatility_pct)
            last *= 1 + ret
            extended.append(last)
        return extended

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "avg_return_pct": self.avg_return_pct,
            "volatility_pct": self.volatility_pct,
            "duration_days": self.duration_days,
        }
