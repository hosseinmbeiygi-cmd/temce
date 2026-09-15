from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class LowVolatilityStrategy(BaseStrategy):
    def __init__(self, lookback: int = 60, vol_percentile: float = 30.0, instrument_id: str = "") -> None:
        super().__init__(name=f"LowVol_{lookback}_{vol_percentile}")
        self.lookback = lookback
        self.vol_percentile = vol_percentile
        self.instrument_id = instrument_id
        self._returns: list[float] = []
        self._position = 0

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        import statistics

        price = bar.get("close", 0)
        if price <= 0:
            return []
        if self._returns:
            daily_ret = (price - self._returns[-1]) / self._returns[-1] if self._returns[-1] > 0 else 0
            self._returns.append(daily_ret)
        else:
            self._returns.append(0.0)
        if len(self._returns) <= self.lookback:
            return []
        recent = self._returns[-self.lookback :]
        vol = statistics.stdev(recent) if len(recent) > 1 else 0.01
        annual_vol = vol * (252**0.5)
        orders: list[OrderEvent] = []
        if annual_vol < 0.15 and self._position <= 0:
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
        elif annual_vol > 0.30 and self._position >= 0:
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
        self._returns.clear()
        self._position = 0
