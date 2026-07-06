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
    ) -> None:
        super().__init__(name=f"HalfTrend_{amplitude}_{channel_deviation}")
        self.amplitude = amplitude
        self.channel_deviation = channel_deviation
        self.instrument_id = instrument_id
        self._highs: list[float] = []
        self._lows: list[float] = []
        self._closes: list[float] = []
        self._position = 0

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        h = bar.get("high", 0)
        l = bar.get("low", 0)
        c = bar.get("close", 0)
        if c <= 0:
            return []

        self._highs.append(h)
        self._lows.append(l)
        self._closes.append(c)

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
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.BUY,
                    quantity=1000,
                    price=c,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._position = 1
        elif sell and self._position >= 0:
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.SELL,
                    quantity=1000,
                    price=c,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._position = -1

        return orders

    def reset(self) -> None:
        self._highs.clear()
        self._lows.clear()
        self._closes.clear()
        self._position = 0
