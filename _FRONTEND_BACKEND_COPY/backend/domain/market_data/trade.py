from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity
from domain.common.enum_types import OrderSide


@dataclass
class Trade(BaseEntity):
    instrument_id: str
    symbol: str = ""
    price: float = 0.0
    volume: int = 0
    value: float = 0.0
    time: str = ""
    date: str = ""
    side: OrderSide | None = None
    data_source: str = "tsetmc"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        symbol: str = "",
        price: float = 0.0,
        volume: int = 0,
        value: float = 0.0,
        time: str = "",
        date: str = "",
        side: OrderSide | None = None,
        data_source: str = "tsetmc",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.price = price
        self.volume = volume
        self.value = value
        self.time = time
        self.date = date
        self.side = side
        self.data_source = data_source
        self.extra = extra or {}
