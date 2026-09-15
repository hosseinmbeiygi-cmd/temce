from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Indicator(BaseEntity):
    instrument_id: str
    name: str
    value: float = 0.0
    symbol: str = ""
    timeframe: str = "1d"
    date: str = ""
    time: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        name: str,
        value: float = 0.0,
        symbol: str = "",
        timeframe: str = "1d",
        date: str = "",
        time: str = "",
        parameters: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.name = name
        self.value = value
        self.symbol = symbol
        self.timeframe = timeframe
        self.date = date
        self.time = time
        self.parameters = parameters or {}
        self.extra = extra or {}
