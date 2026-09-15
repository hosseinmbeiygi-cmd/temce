from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RecommendationExplanation:
    summary: str = ""
    factors: list[dict[str, Any]] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    technical_analysis: str = ""
    fundamental_analysis: str = ""
    market_outlook: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
