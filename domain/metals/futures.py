from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class MetalFutures(BaseEntity):
    metal_id: str
    contract_code: str = ""
    delivery_month: str = ""
    delivery_year: int = 0
    delivery_date: date | None = None
    last_trade_date: date | None = None
    price: float = 0.0
    volume: int = 0
    open_interest: int = 0
    status: str = "active"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        metal_id: str,
        contract_code: str = "",
        delivery_month: str = "",
        delivery_year: int = 0,
        delivery_date: date | None = None,
        last_trade_date: date | None = None,
        price: float = 0.0,
        volume: int = 0,
        open_interest: int = 0,
        status: str = "active",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.metal_id = metal_id
        self.contract_code = contract_code
        self.delivery_month = delivery_month
        self.delivery_year = delivery_year
        self.delivery_date = delivery_date
        self.last_trade_date = last_trade_date
        self.price = price
        self.volume = volume
        self.open_interest = open_interest
        self.status = status
        self.extra = extra or {}
