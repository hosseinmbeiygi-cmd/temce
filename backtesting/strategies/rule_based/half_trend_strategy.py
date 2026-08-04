from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType
from src.indicators.trend_momentum import calculate_half_trend


class HalfTrendStrategy(BaseStrategy):
    def __init__(
        self,
        amplitude: int = 2,
        channel_deviation: float = 2.0,
        instrument_id: str = "",
        sizing_method: str = "fixed",
        sizing_value: float = 1000.0,
    ) -> None:
        super().__init__(name=f"HalfTrend_{amplitude}_{channel_deviation}",
                         sizing_method=sizing_method, sizing_value=sizing_value)
        self.amplitude = amplitude
        self.channel_deviation = channel_deviation
        self.instrument_id = instrument_id
        self._highs: list[float] = []
        self._lows: list[float] = []
        self._closes: list[float] = []
        self._position = 0

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        high = bar.get("high", 0)
        low = bar.get("low", 0)
        close = bar.get("close", 0)
        if close <= 0:
            return []

        self._highs.append(high)
        self._lows.append(low)
        self._closes.append(close)

        if len(self._closes) < self.amplitude + 1:
            return []

        result = calculate_half_trend(
            self._highs,
            self._lows,
            self._closes,
            amplitude=self.amplitude,
            channel_deviation=self.channel_deviation,
        )

        buy = result["buy_signal"][-1]
        sell = result["sell_signal"][-1]
        orders: list[OrderEvent] = []

        if buy and self._position <= 0:
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
        elif sell and self._position > 0:
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
        self._position = 0
