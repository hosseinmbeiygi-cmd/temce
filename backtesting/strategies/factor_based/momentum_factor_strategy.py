from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class MomentumFactorStrategy(BaseStrategy):
    def __init__(self, short_lookback: int = 60, long_lookback: int = 252, instrument_id: str = "") -> None:
        super().__init__(name=f"MomentumFactor_{short_lookback}_{long_lookback}")
        self.short_lookback = short_lookback
        self.long_lookback = long_lookback
        self.instrument_id = instrument_id
        self._prices: list[float] = []
        self._position = 0

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        price = bar.get("close", 0)
        if price <= 0:
            return []
        self._prices.append(price)
        if len(self._prices) <= self.long_lookback:
            return []
        short_ret = (price - self._prices[-self.short_lookback]) / self._prices[-self.short_lookback]
        long_ret = (price - self._prices[-self.long_lookback]) / self._prices[-self.long_lookback]
        momentum_score = short_ret + long_ret
        orders: list[OrderEvent] = []
        if momentum_score > 0 and self._position <= 0:
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
        elif momentum_score < 0 and self._position >= 0:
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
