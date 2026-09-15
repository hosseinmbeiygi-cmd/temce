from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RISK_LABEL_VERY_LOW = "very_low"
RISK_LABEL_LOW = "low"
RISK_LABEL_MEDIUM = "medium"
RISK_LABEL_HIGH = "high"
RISK_LABEL_VERY_HIGH = "very_high"


@dataclass
class RiskLabel:
    level: str = "medium"
    score: float = 0.0
    description: str = ""
    factors: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_high_risk(self) -> bool:
        return self.level in (RISK_LABEL_HIGH, RISK_LABEL_VERY_HIGH)

    @property
    def is_low_risk(self) -> bool:
        return self.level in (RISK_LABEL_LOW, RISK_LABEL_VERY_LOW)
