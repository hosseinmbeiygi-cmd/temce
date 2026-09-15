from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LowLiquidityScenario:
    name: str = "low_liquidity"
    volume_reduction_pct: float = 0.7
    spread_multiplier: float = 3.0
    duration_days: int = 63

    def apply_volume(self, volumes: list[float]) -> list[float]:
        import numpy as np

        if not volumes:
            return []
        extended = list(volumes)
        for _ in range(self.duration_days):
            reduced = np.random.poisson(np.mean(volumes) * (1 - self.volume_reduction_pct))
            extended.append(max(0, reduced))
        return extended

    def apply_spread(self, prices: list[float]) -> list[float]:
        if not prices:
            return []
        return [p * self.spread_multiplier for p in prices]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "volume_reduction_pct": self.volume_reduction_pct,
            "spread_multiplier": self.spread_multiplier,
            "duration_days": self.duration_days,
        }
