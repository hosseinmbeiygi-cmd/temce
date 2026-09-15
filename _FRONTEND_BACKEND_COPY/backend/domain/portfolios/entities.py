from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class PortfolioTransaction(BaseEntity):
    portfolio_id: str
    instrument_id: str
    transaction_type: str
    symbol: str = ""
    quantity: int = 0
    price: float = 0.0
    value: float = 0.0
    commission: float = 0.0
    tax: float = 0.0
    date: str = ""
    time: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        portfolio_id: str,
        instrument_id: str,
        transaction_type: str,
        symbol: str = "",
        quantity: int = 0,
        price: float = 0.0,
        value: float = 0.0,
        commission: float = 0.0,
        tax: float = 0.0,
        date: str = "",
        time: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.portfolio_id = portfolio_id
        self.instrument_id = instrument_id
        self.transaction_type = transaction_type
        self.symbol = symbol
        self.quantity = quantity
        self.price = price
        self.value = value
        self.commission = commission
        self.tax = tax
        self.date = date
        self.time = time
        self.extra = extra or {}

    @property
    def net_value(self) -> float:
        return self.value - self.commission - self.tax
