from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class EnergyInstrument(BaseEntity):
    name: str
    symbol: str = ""
    energy_type: str = ""
    unit: str = ""
    currency: str = "USD"
    exchange: str = ""
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        symbol: str = "",
        energy_type: str = "",
        unit: str = "",
        currency: str = "USD",
        exchange: str = "",
        is_active: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.symbol = symbol
        self.energy_type = energy_type
        self.unit = unit
        self.currency = currency
        self.exchange = exchange
        self.is_active = is_active
        self.extra = extra or {}


@dataclass
class EnergyTrade(BaseEntity):
    instrument_id: str
    price: float = 0.0
    volume: float = 0.0
    value: float = 0.0
    time: str = ""
    date: str = ""
    side: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        price: float = 0.0,
        volume: float = 0.0,
        value: float = 0.0,
        time: str = "",
        date: str = "",
        side: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.price = price
        self.volume = volume
        self.value = value
        self.time = time
        self.date = date
        self.side = side
        self.extra = extra or {}
