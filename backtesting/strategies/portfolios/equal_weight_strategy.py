from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class EqualWeightStrategy(BaseStrategy):
    def __init__(self, instrument_ids: list[str] | None = None, capital_per_instrument: float = 0.0) -> None:
        super().__init__(name="EqualWeight")
        self.instrument_ids = instrument_ids or []
        self.capital_per_instrument = capital_per_instrument
        self._allocated: dict[str, bool] = {}

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        orders: list[OrderEvent] = []
        for inst_id in self.instrument_ids:
            if not self._allocated.get(inst_id, False):
                price = (
                    bar.get("close", 0)
                    if isinstance(bar.get("close"), (int, float))
                    else bar.get(inst_id, {}).get("close", 0)
                )
                if price > 0:
                    qty = int(self.capital_per_instrument / price) if self.capital_per_instrument > 0 else 100
                    if qty > 0:
                        orders.append(
                            OrderEvent(
                                instrument_id=inst_id,
                                side=OrderSide.BUY,
                                quantity=qty,
                                price=price,
                                order_type=OrderType.MARKET,
                                order_id=new_id("ord"),
                            )
                        )
                        self._allocated[inst_id] = True
        return orders

    def reset(self) -> None:
        self._allocated.clear()
