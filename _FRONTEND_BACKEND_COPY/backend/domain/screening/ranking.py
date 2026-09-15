from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScreeningResult:
    instrument_id: str = ""
    symbol: str = ""
    name: str = ""
    score: float = 0.0
    rank: int = 0
    matched_filters: int = 0
    total_filters: int = 0
    values: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def match_rate(self) -> float:
        if self.total_filters == 0:
            return 1.0
        return self.matched_filters / self.total_filters

    @property
    def is_top_ranked(self) -> bool:
        return self.rank <= 10
