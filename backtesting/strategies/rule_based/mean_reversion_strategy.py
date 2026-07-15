from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class MeanReversionStrategy(BaseStrategy):
    def __init__(self, lookback: int = 20, entry_z: float = 2.0, exit_z: float = 0.5, instrument_id: str = "",
                 sizing_method: str = "fixed", sizing_value: float = 1000.0) -> None:
        super().__init__(name=f"MeanReversion_{lookback}",
                         sizing_method=sizing_method, sizing_value=sizing_value)
        self.lookback = lookback
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.instrument_id = instrument_id
        self._prices: list[float] = []
        self._position = 0

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        import statistics

        price = bar.get("close", 0)
        if price <= 0:
            return []
        self._prices.append(price)
        if len(self._prices) <= self.lookback:
            return []
        recent = self._prices[-self.lookback:]
        mean = statistics.mean(recent)
        std = statistics.stdev(recent) if len(recent) > 1 else 1.0
        z_score = (price - mean) / std if std > 0 else 0
        orders: list[OrderEvent] = []
        if z_score > self.entry_z and self._position > 0:
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
        elif z_score < -self.entry_z and self._position <= 0:
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
        elif abs(z_score) < self.exit_z and self._position != 0:
            side = OrderSide.SELL if self._position > 0 else OrderSide.BUY
            qty = self._compute_quantity(price)
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=side,
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
