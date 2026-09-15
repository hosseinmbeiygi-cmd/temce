from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from domain.common.enum_types import OrderSide, OrderType


@dataclass
class Order:
    instrument_id: str
    side: OrderSide
    quantity: int
    price: float
    order_type: OrderType = OrderType.MARKET
    order_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_valid(self) -> bool:
        return self.quantity > 0 and self.price >= 0


@dataclass
class MarketOrder(Order):
    order_type: OrderType = OrderType.MARKET
    price: float = 0.0


@dataclass
class LimitOrder(Order):
    order_type: OrderType = OrderType.LIMIT
    time_in_force: str = "day"


@dataclass
class StopOrder(Order):
    order_type: OrderType = OrderType.STOP_LOSS
    stop_price: float = 0.0
