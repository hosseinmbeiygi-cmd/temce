from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class VolatilityBreakoutStrategy(BaseStrategy):
    def __init__(self, lookback: int = 20, multiplier: float = 2.0, instrument_id: str = "") -> None:
        super().__init__(name=f"VolBreakout_{lookback}_{multiplier}")
        self.lookback = lookback
        self.multiplier = multiplier
        self.instrument_id = instrument_id
        self._highs: list[float] = []
        self._lows: list[float] = []
        self._closes: list[float] = []
        self._position = 0

    def _compute_atr(self) -> float:
        if len(self._highs) < 2:
            return 0.0
        trs = []
        for i in range(1, len(self._highs)):
            hl = self._highs[i] - self._lows[i]
            hc = abs(self._highs[i] - self._closes[i - 1]) if len(self._closes) > i else 0
            lc = abs(self._lows[i] - self._closes[i - 1]) if len(self._closes) > i else 0
            trs.append(max(hl, hc, lc))
        if not trs:
            return 0.0
        return sum(trs[-self.lookback :]) / min(len(trs), self.lookback)

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        high = bar.get("high", 0)
        low = bar.get("low", 0)
        close = bar.get("close", 0)
        if high <= 0 or low <= 0 or close <= 0:
            return []
        self._highs.append(high)
        self._lows.append(low)
        self._closes.append(close)
        if len(self._highs) <= self.lookback:
            return []
        atr = self._compute_atr()
        if atr <= 0:
            return []
        upper = self._closes[-2] + self.multiplier * atr if len(self._closes) >= 2 else close + atr
        lower = self._closes[-2] - self.multiplier * atr if len(self._closes) >= 2 else close - atr
        orders: list[OrderEvent] = []
        if close > upper and self._position <= 0:
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
        elif close < lower and self._position >= 0:
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
        self._closes.clear()
        self._position = 0
