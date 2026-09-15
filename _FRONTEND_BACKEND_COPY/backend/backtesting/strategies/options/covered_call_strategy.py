from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class CoveredCallStrategy(BaseStrategy):
    def __init__(self, call_strike: float = 0.0, call_premium: float = 0.0, instrument_id: str = "") -> None:
        super().__init__(name="CoveredCall")
        self.call_strike = call_strike
        self.call_premium = call_premium
        self.instrument_id = instrument_id
        self._has_shares = False

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        price = bar.get("close", 0)
        if price <= 0:
            return []
        orders: list[OrderEvent] = []
        if not self._has_shares:
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
            self._has_shares = True
        return orders

    def reset(self) -> None:
        self._has_shares = False
