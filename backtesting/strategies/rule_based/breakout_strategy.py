from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class BreakoutStrategy(BaseStrategy):
    def __init__(self, lookback: int = 20, breakout_pct: float = 0.0, instrument_id: str = "") -> None:
        super().__init__(name=f"Breakout_{lookback}")
        self.lookback = lookback
        self.breakout_pct = breakout_pct
        self.instrument_id = instrument_id
        self._highs: list[float] = []
        self._lows: list[float] = []
        self._position = 0

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        high = bar.get("high", 0)
        low = bar.get("low", 0)
        close = bar.get("close", 0)
        if high <= 0 or low <= 0:
            return []
        self._highs.append(high)
        self._lows.append(low)
        if len(self._highs) <= self.lookback:
            return []
        resistance = max(self._highs[-self.lookback - 1 : -1]) * (1 + self.breakout_pct / 100)
        support = min(self._lows[-self.lookback - 1 : -1]) * (1 - self.breakout_pct / 100)
        orders: list[OrderEvent] = []
        if close > resistance and self._position <= 0:
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.BUY,
                    quantity=1000,
                    price=close,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._position = 1
        elif close < support and self._position >= 0:
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.SELL,
                    quantity=1000,
                    price=close,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._position = -1
        return orders

    def reset(self) -> None:
        self._highs.clear()
        self._lows.clear()
        self._position = 0
