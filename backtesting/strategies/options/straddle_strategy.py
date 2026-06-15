from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class StraddleStrategy(BaseStrategy):
    def __init__(self, atm_strike: float = 0.0, premium_cost: float = 0.0, instrument_id: str = "") -> None:
        super().__init__(name="Straddle")
        self.atm_strike = atm_strike
        self.premium_cost = premium_cost
        self.instrument_id = instrument_id
        self._in_position = False

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        price = bar.get("close", 0)
        if price <= 0:
            return []
        orders: list[OrderEvent] = []
        if not self._in_position:
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.BUY,
                    quantity=1000,
                    price=price,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._in_position = True
        return orders

    def reset(self) -> None:
        self._in_position = False
