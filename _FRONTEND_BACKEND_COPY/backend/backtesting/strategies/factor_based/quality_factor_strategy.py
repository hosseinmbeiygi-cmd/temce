from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class QualityFactorStrategy(BaseStrategy):
    def __init__(self, roe_threshold: float = 15.0, de_threshold: float = 1.0, instrument_id: str = "") -> None:
        super().__init__(name=f"QualityFactor_ROE{roe_threshold}")
        self.roe_threshold = roe_threshold
        self.de_threshold = de_threshold
        self.instrument_id = instrument_id
        self._position = 0

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        price = bar.get("close", 0)
        roe = bar.get("roe", 0)
        de_ratio = bar.get("de_ratio", 999)
        if price <= 0:
            return []
        quality_score = 0
        if roe > self.roe_threshold:
            quality_score += 1
        if de_ratio < self.de_threshold:
            quality_score += 1
        orders: list[OrderEvent] = []
        if quality_score >= 2 and self._position <= 0:
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
        elif quality_score < 1 and self._position >= 0:
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
        self._position = 0
