from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class ForecastSignalStrategy(BaseStrategy):
    def __init__(self, model=None, instrument_id: str = "") -> None:
        super().__init__(name="ForecastSignal")
        self.model = model
        self.instrument_id = instrument_id
        self._position = 0

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        price = bar.get("close", 0)
        if price <= 0:
            return []
        if self.model is None:
            return []
        features = self._extract_features(bar)
        forecast = self.model.predict([features])[0] if hasattr(self.model, "predict") else 0.0
        forecast_return = (forecast - price) / price if price > 0 else 0
        orders: list[OrderEvent] = []
        if forecast_return > 0.01 and self._position <= 0:
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
        elif forecast_return < -0.01 and self._position >= 0:
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

    def _extract_features(self, bar: dict[str, Any]) -> list[float]:
        return [bar.get(k, 0.0) for k in ["close", "volume", "open", "high", "low"]]

    def reset(self) -> None:
        self._position = 0
