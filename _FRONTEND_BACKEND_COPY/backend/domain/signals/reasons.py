from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REASON_TECHNICAL = "technical"
REASON_FUNDAMENTAL = "fundamental"
REASON_NEWS = "news"
REASON_MACRO = "macro"
REASON_SENTIMENT = "sentiment"
REASON_PATTERN = "pattern"
REASON_VOLUME = "volume"
REASON_MOMENTUM = "momentum"
REASON_TREND = "trend"
REASON_CUSTOM = "custom"


@dataclass
class SignalReason:
    reason_type: str = ""
    description: str = ""
    weight: float = 1.0
    score: float = 0.0
    indicators: dict[str, Any] = field(default_factory=dict)
