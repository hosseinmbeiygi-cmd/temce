from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class ValueFactorStrategy(BaseStrategy):
    def __init__(self, pe_threshold: float = 15.0, pb_threshold: float = 1.5, instrument_id: str = "") -> None:
        super().__init__(name=f"ValueFactor_PE{pe_threshold}_PB{pb_threshold}")
        self.pe_threshold = pe_threshold
        self.pb_threshold = pb_threshold
        self.instrument_id = instrument_id
        self._position = 0

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        price = bar.get("close", 0)
        pe = bar.get("pe_ratio", 0)
        pb = bar.get("pb_ratio", 0)
        if price <= 0 or pe <= 0 or pb <= 0:
            return []
        value_score = 0
        if pe < self.pe_threshold:
            value_score += 1
        if pb < self.pb_threshold:
            value_score += 1
        orders: list[OrderEvent] = []
        if value_score >= 2 and self._position <= 0:
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
        elif value_score < 1 and self._position >= 0:
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
