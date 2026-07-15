from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class RSIMeanReversionStrategy(BaseStrategy):
    def __init__(
        self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0, instrument_id: str = "",
        sizing_method: str = "fixed", sizing_value: float = 1000.0,
    ) -> None:
        super().__init__(name=f"RSI_{period}_{oversold}_{overbought}",
                         sizing_method=sizing_method, sizing_value=sizing_value)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.instrument_id = instrument_id
        self._prices: list[float] = []
        self._position = 0

    def _compute_rsi(self) -> float:
        if len(self._prices) < self.period + 1:
            return 50.0
        deltas = [self._prices[i] - self._prices[i - 1] for i in range(1, len(self._prices))]
        gains = [d if d > 0 else 0.0 for d in deltas[-(self.period + 1):]]
        losses = [-d if d < 0 else 0.0 for d in deltas[-(self.period + 1):]]
        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        price = bar.get("close", 0)
        if price <= 0:
            return []
        self._prices.append(price)
        if len(self._prices) <= self.period:
            return []
        rsi = self._compute_rsi()
        orders: list[OrderEvent] = []
        if rsi < self.oversold and self._position <= 0:
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
        elif rsi > self.overbought and self._position > 0:
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
