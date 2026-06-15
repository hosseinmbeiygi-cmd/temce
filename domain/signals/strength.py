from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SignalStrength:
    score: float = 0.0
    level: str = "moderate"
    components: dict[str, float] = field(default_factory=dict)
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.score >= 0.8:
            self.level = "strong"
        elif self.score >= 0.5:
            self.level = "moderate"
        else:
            self.level = "weak"

    @property
    def is_strong(self) -> bool:
        return self.score >= 0.8

    @property
    def is_weak(self) -> bool:
        return self.score < 0.5
