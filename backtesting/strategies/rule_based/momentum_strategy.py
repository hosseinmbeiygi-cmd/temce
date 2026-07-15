from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class MomentumStrategy(BaseStrategy):
    def __init__(self, lookback: int = 20, threshold_pct: float = 5.0, instrument_id: str = "",
                 sizing_method: str = "fixed", sizing_value: float = 1000.0) -> None:
        super().__init__(name=f"Momentum_{lookback}_{threshold_pct}",
                         sizing_method=sizing_method, sizing_value=sizing_value)
        self.lookback = lookback
        self.threshold_pct = threshold_pct
        self.instrument_id = instrument_id
        self._prices: list[float] = []
        self._position = 0

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        price = bar.get("close", 0)
        if price <= 0:
            return []
        self._prices.append(price)
        if len(self._prices) <= self.lookback:
            return []
        start_price = self._prices[-self.lookback - 1]
        momentum = ((price - start_price) / start_price * 100) if start_price else 0.0
        orders: list[OrderEvent] = []
        if momentum > self.threshold_pct and self._position <= 0:
            qty = self._compute_quantity(price)
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.BUY,
                    quantity=qty,
                    price=price,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._position = 1
        elif momentum < -self.threshold_pct and self._position > 0:
            qty = self._compute_quantity(price)
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.SELL,
                    quantity=qty,
                    price=price,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._position = 0
        return orders

    def reset(self) -> None:
        self._prices.clear()
        self._position = 0
