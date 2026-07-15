from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType
from src.indicators.trend_momentum import calculate_squeeze_momentum


class SqueezeMomentumStrategy(BaseStrategy):
    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        kc_period: int = 20,
        kc_mult: float = 1.5,
        instrument_id: str = "",
        sizing_method: str = "fixed",
        sizing_value: float = 1000.0,
    ) -> None:
        super().__init__(name=f"SqueezeMomentum_{bb_period}_{kc_period}",
                         sizing_method=sizing_method, sizing_value=sizing_value)
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.kc_period = kc_period
        self.kc_mult = kc_mult
        self.instrument_id = instrument_id
        self._highs: list[float] = []
        self._lows: list[float] = []
        self._closes: list[float] = []
        self._position = 0
        self._was_squeezing = False

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        h = bar.get("high", 0)
        l = bar.get("low", 0)
        c = bar.get("close", 0)
        if c <= 0:
            return []

        self._highs.append(h)
        self._lows.append(l)
        self._closes.append(c)

        min_len = max(self.bb_period, self.kc_period) + 1
        if len(self._closes) < min_len:
            return []

        result = calculate_squeeze_momentum(
            self._highs,
            self._lows,
            self._closes,
            bb_period=self.bb_period,
            bb_std=self.bb_std,
            kc_period=self.kc_period,
            kc_mult=self.kc_mult,
        )

        is_squeezing = result["squeeze_on"][-1]
        mom_positive = result["momentum_positive"][-1]
        orders: list[OrderEvent] = []

        if self._was_squeezing and not is_squeezing and mom_positive and self._position <= 0:
            qty = self._compute_quantity(c)
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.BUY,
                    quantity=qty,
                    price=c,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._position = 1
        elif not mom_positive and self._position > 0 and not is_squeezing:
            qty = self._compute_quantity(c)
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.SELL,
                    quantity=qty,
                    price=c,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._position = 0

        self._was_squeezing = is_squeezing
        return orders

    def reset(self) -> None:
        self._highs.clear()
        self._lows.clear()
        self._closes.clear()
        self._position = 0
        self._was_squeezing = False
