from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class SpotPrice(BaseEntity):
    metal_id: str
    price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    currency: str = "USD"
    unit: str = "oz"
    date: str = ""
    time: str = ""
    source: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        metal_id: str,
        price: float = 0.0,
        bid: float = 0.0,
        ask: float = 0.0,
        currency: str = "USD",
        unit: str = "oz",
        date: str = "",
        time: str = "",
        source: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.metal_id = metal_id
        self.price = price
        self.bid = bid
        self.ask = ask
        self.currency = currency
        self.unit = unit
        self.date = date
        self.time = time
        self.source = source
        self.extra = extra or {}
