from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class EnergyContract(BaseEntity):
    instrument_id: str
    contract_code: str = ""
    delivery_month: str = ""
    delivery_year: int = 0
    delivery_start: date | None = None
    delivery_end: date | None = None
    price: float = 0.0
    volume: float = 0.0
    unit: str = ""
    status: str = "active"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        contract_code: str = "",
        delivery_month: str = "",
        delivery_year: int = 0,
        delivery_start: date | None = None,
        delivery_end: date | None = None,
        price: float = 0.0,
        volume: float = 0.0,
        unit: str = "",
        status: str = "active",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.contract_code = contract_code
        self.delivery_month = delivery_month
        self.delivery_year = delivery_year
        self.delivery_start = delivery_start
        self.delivery_end = delivery_end
        self.price = price
        self.volume = volume
        self.unit = unit
        self.status = status
        self.extra = extra or {}
