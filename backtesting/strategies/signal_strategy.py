from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class SignalStrategy(BaseStrategy):
    """Strategy driven by pre-computed entry/exit signal arrays.

    For each bar at index i, checks entry_signal[i] and exit_signal[i].
    Avoids look-ahead because signals are pre-computed from past data only.
    """

    def __init__(
        self,
        entry_signal: list[bool],
        exit_signal: list[bool],
        name: str = "Signal",
        instrument_id: str = "",
        sizing_method: str = "fixed",
        sizing_value: float = 1000.0,
    ) -> None:
        super().__init__(name=name, sizing_method=sizing_method, sizing_value=sizing_value)
        self._entry = entry_signal
        self._exit = exit_signal
        self.instrument_id = instrument_id
        self._idx = 0
        self._in_position = False
        self._position_qty = 0

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        price = bar.get("close", 0)
        if price <= 0:
            self._idx += 1
            return []

        orders: list[OrderEvent] = []

        if not self._in_position and self._idx < len(self._entry) and self._entry[self._idx]:
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
            self._in_position = True
            self._position_qty = qty

        elif self._in_position and self._idx < len(self._exit) and self._exit[self._idx]:
            qty = self._position_qty
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
            self._in_position = False
            self._position_qty = 0

        self._idx += 1
        return orders

    def reset(self) -> None:
        self._idx = 0
        self._in_position = False
        self._position_qty = 0
