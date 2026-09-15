from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketClassification:
    market_type: str = ""
    region: str = ""
    country: str = ""
    currency: str = ""
    timezone: str = ""
    opening_time: str = ""
    closing_time: str = ""
    settlement_cycle: str = "T+2"
    trading_currency: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
