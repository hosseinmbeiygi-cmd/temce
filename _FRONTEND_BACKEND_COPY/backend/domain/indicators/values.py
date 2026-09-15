from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class IndicatorValueHistory(BaseEntity):
    indicator_id: str
    instrument_id: str
    values: list[dict[str, Any]] = field(default_factory=list)
    timeframe: str = "1d"
    date: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        indicator_id: str,
        instrument_id: str,
        values: list[dict[str, Any]] | None = None,
        timeframe: str = "1d",
        date: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.indicator_id = indicator_id
        self.instrument_id = instrument_id
        self.values = values or []
        self.timeframe = timeframe
        self.date = date
        self.extra = extra or {}

    def add_value(self, timestamp: str, value: float) -> None:
        self.values.append({"timestamp": timestamp, "value": value})
        self.mark_updated()
