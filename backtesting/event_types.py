"""Market event types shared by engine, strategies and microstructure.

Kept outside ``backtesting.engine`` so lower-level packages can use them without
importing the engine package (AUD-ARCH-01). ``engine.event_builder`` re-exports
these names for existing callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    TRADE = "TRADE"
    QUOTE = "QUOTE"
    AUCTION = "AUCTION"
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"
    STATUS_CHANGE = "STATUS_CHANGE"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    ORDERBOOK_SNAPSHOT = "ORDERBOOK_SNAPSHOT"


@dataclass
class MarketEvent:
    event_id: str
    timestamp: datetime
    instrument_id: str
    market_id: str
    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 0

    def __lt__(self, other: MarketEvent) -> bool:
        if self.timestamp == other.timestamp:
            return self.priority < other.priority
        return self.timestamp < other.timestamp
