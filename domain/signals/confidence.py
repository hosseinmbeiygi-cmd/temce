from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SignalConfidence:
    score: float = 0.0
    level: str = "medium"
    factors: dict[str, float] = field(default_factory=dict)
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.score >= 0.8:
            self.level = "high"
        elif self.score >= 0.5:
            self.level = "medium"
        else:
            self.level = "low"

    @property
    def is_high(self) -> bool:
        return self.score >= 0.8

    @property
    def is_low(self) -> bool:
        return self.score < 0.5
