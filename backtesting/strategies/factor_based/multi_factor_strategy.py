from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class MultiFactorStrategy(BaseStrategy):
    def __init__(self, instrument_id: str = "") -> None:
        super().__init__(name="MultiFactor")
        self.instrument_id = instrument_id
        self._factors: dict[str, float] = {}

    def add_factor(self, name: str, weight: float) -> None:
        self._factors[name] = weight

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        score = 0.0
        for factor_name, weight in self._factors.items():
            value = bar.get(factor_name, 0)
            score += value * weight
        price = bar.get("close", 0)
        if price <= 0:
            return []
        threshold = bar.get("threshold", 0.5)
        if score > threshold:
            return [
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.BUY,
                    quantity=1000,
                    price=price,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            ]
        elif score < -threshold:
            return [
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.SELL,
                    quantity=1000,
                    price=price,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            ]
        return []

    def reset(self) -> None:
        pass
