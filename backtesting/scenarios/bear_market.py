from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.trading_constants import TRADING_DAYS_PER_YEAR_GLOBAL


@dataclass
class BearMarketScenario:
    name: str = "bear_market"
    avg_return_pct: float = -0.20
    volatility_pct: float = 0.03
    duration_days: int = TRADING_DAYS_PER_YEAR_GLOBAL

    def apply(self, prices: list[float]) -> list[float]:
        import numpy as np

        if not prices:
            return []
        last = prices[-1]
        extended = list(prices)
        daily_return = self.avg_return_pct / TRADING_DAYS_PER_YEAR_GLOBAL
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
