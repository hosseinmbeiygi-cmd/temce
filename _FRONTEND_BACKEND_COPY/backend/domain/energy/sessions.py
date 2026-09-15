from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class TradingSession(BaseEntity):
    instrument_id: str
    session_date: date | None = None
    open_time: str = ""
    close_time: str = ""
    status: str = "scheduled"
    volume: float = 0.0
    avg_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    close_price: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        session_date: date | None = None,
        open_time: str = "",
        close_time: str = "",
        status: str = "scheduled",
        volume: float = 0.0,
        avg_price: float = 0.0,
        high_price: float = 0.0,
        low_price: float = 0.0,
        close_price: float = 0.0,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.session_date = session_date
        self.open_time = open_time
        self.close_time = close_time
        self.status = status
        self.volume = volume
        self.avg_price = avg_price
        self.high_price = high_price
        self.low_price = low_price
        self.close_price = close_price
        self.extra = extra or {}

    def open(self) -> None:
        self.status = "open"
        self.mark_updated()

    def close(self) -> None:
        self.status = "closed"
        self.mark_updated()
