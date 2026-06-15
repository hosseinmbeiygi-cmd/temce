from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketBreadth:
    advancing: int = 0
    declining: int = 0
    unchanged: int = 0
    total: int = 0
    adv_volume: int = 0
    dec_volume: int = 0
    adv_value: float = 0.0
    dec_value: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def advance_decline_ratio(self) -> float:
        if self.declining == 0:
            return float(self.advancing) if self.advancing > 0 else 1.0
        return self.advancing / self.declining

    @property
    def advance_decline_line(self) -> int:
        return self.advancing - self.declining

    @property
    def percent_advancing(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.advancing / self.total) * 100.0
