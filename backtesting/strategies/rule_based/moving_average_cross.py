from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class MovingAverageCrossStrategy(BaseStrategy):
    def __init__(self, fast_period: int = 5, slow_period: int = 20, instrument_id: str = "") -> None:
        super().__init__(name=f"MA_Cross_{fast_period}_{slow_period}")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.instrument_id = instrument_id
        self._prices: list[float] = []
        self._position = 0

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        price = bar.get("close", 0)
        if price <= 0:
            return []
        self._prices.append(price)
        if len(self._prices) < self.slow_period:
            return []
        fast_ma = sum(self._prices[-self.fast_period :]) / self.fast_period
        slow_ma = sum(self._prices[-self.slow_period :]) / self.slow_period
        orders: list[OrderEvent] = []
        if fast_ma > slow_ma and self._position <= 0:
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
            self._position = 1
        elif fast_ma < slow_ma and self._position >= 0:
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.SELL,
                    quantity=1000,
                    price=price,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._position = -1
        return orders

    def reset(self) -> None:
        self._prices.clear()
        self._position = 0
