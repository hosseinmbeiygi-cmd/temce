from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class FuturesContract(BaseEntity):
    commodity_id: str
    contract_code: str = ""
    symbol: str = ""
    delivery_date: date | None = None
    last_trade_date: date | None = None
    settlement_date: date | None = None
    contract_size: int = 1
    tick_size: float = 0.01
    price: float = 0.0
    volume: int = 0
    open_interest: int = 0
    status: str = "active"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        commodity_id: str,
        contract_code: str = "",
        symbol: str = "",
        delivery_date: date | None = None,
        last_trade_date: date | None = None,
        settlement_date: date | None = None,
        contract_size: int = 1,
        tick_size: float = 0.01,
        price: float = 0.0,
        volume: int = 0,
        open_interest: int = 0,
        status: str = "active",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.commodity_id = commodity_id
        self.contract_code = contract_code
        self.symbol = symbol
        self.delivery_date = delivery_date
        self.last_trade_date = last_trade_date
        self.settlement_date = settlement_date
        self.contract_size = contract_size
        self.tick_size = tick_size
        self.price = price
        self.volume = volume
        self.open_interest = open_interest
        self.status = status
        self.extra = extra or {}

    @property
    def is_settled(self) -> bool:
        return self.status == "settled"

    def settle(self) -> None:
        self.status = "settled"
        self.mark_updated()
