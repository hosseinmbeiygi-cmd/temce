from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class DomainEvent:
    event_id: str = ""
    event_type: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any] = field(default_factory=dict)


class MarketEvents:
    QUOTE_UPDATED = "quote.updated"
    INSTRUMENT_CREATED = "instrument.created"
    SIGNAL_GENERATED = "signal.generated"
    TRADE_EXECUTED = "trade.executed"
    MODEL_TRAINED = "model.trained"
    BACKTEST_COMPLETED = "backtest.completed"
    DATA_INGESTED = "data.ingested"
    ALERT_TRIGGERED = "alert.triggered"
