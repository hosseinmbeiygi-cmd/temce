from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType
from src.indicators.trend_momentum import calculate_support_resistance


class SupportResistanceStrategy(BaseStrategy):
    def __init__(
        self,
        lookback: int = 20,
        vol_threshold: float = 1.5,
        instrument_id: str = "",
        sizing_method: str = "fixed",
        sizing_value: float = 1000.0,
    ) -> None:
        super().__init__(name=f"SupportResistance_{lookback}",
                         sizing_method=sizing_method, sizing_value=sizing_value)
        self.lookback = lookback
        self.vol_threshold = vol_threshold
        self.instrument_id = instrument_id
        self._highs: list[float] = []
        self._lows: list[float] = []
        self._closes: list[float] = []
        self._volumes: list[float] = []
        self._position = 0

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        high = bar.get("high", 0)
        low = bar.get("low", 0)
        close = bar.get("close", 0)
        volume = bar.get("volume", 0)
        if close <= 0:
            return []

        self._highs.append(high)
        self._lows.append(low)
        self._closes.append(close)
        self._volumes.append(volume)

        if len(self._closes) < self.lookback + 1:
            return []

        result = calculate_support_resistance(
            self._highs,
            self._lows,
            self._closes,
            lookback=self.lookback,
            volume=self._volumes,
            vol_threshold=self.vol_threshold,
        )

        is_break_up = result["break_up"][-1]
        is_break_down = result["break_down"][-1]
        is_pullback = result["pullback"][-1]
        orders: list[OrderEvent] = []

        if (is_break_up or is_pullback) and self._position <= 0:
            qty = self._compute_quantity(close)
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.BUY,
                    quantity=qty,
                    price=close,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._position = 1
        elif is_break_down and self._position > 0:
            qty = self._compute_quantity(close)
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.SELL,
                    quantity=qty,
                    price=close,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._position = 0

        return orders

    def reset(self) -> None:
        self._highs.clear()
        self._lows.clear()
        self._closes.clear()
        self._volumes.clear()
        self._position = 0
