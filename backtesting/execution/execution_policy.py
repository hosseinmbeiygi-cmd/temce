from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backtesting.execution.order_models import Order
from backtesting.types import FillEvent
from domain.common.enum_types import OrderSide


class ExecutionPolicy(ABC):
    @abstractmethod
    def execute(self, order: Order, market_data: dict[str, Any]) -> FillEvent | None: ...


class MarketExecutionPolicy(ExecutionPolicy):
    def execute(self, order: Order, market_data: dict[str, Any]) -> FillEvent | None:
        price = market_data.get("close", order.price)
        return FillEvent(
            order_id=order.order_id,
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=order.quantity,
            price=price,
            commission=0.0,
        )


class LimitExecutionPolicy(ExecutionPolicy):
    def execute(self, order: Order, market_data: dict[str, Any]) -> FillEvent | None:
        high = market_data.get("high", order.price)
        low = market_data.get("low", order.price)
        if order.side == OrderSide.BUY and low <= order.price:
            fill_price = min(order.price, high)
            return FillEvent(
                order_id=order.order_id,
                instrument_id=order.instrument_id,
                side=order.side,
                quantity=order.quantity,
                price=fill_price,
                commission=0.0,
            )
        if order.side == OrderSide.SELL and high >= order.price:
            fill_price = max(order.price, low)
            return FillEvent(
                order_id=order.order_id,
                instrument_id=order.instrument_id,
                side=order.side,
                quantity=order.quantity,
                price=fill_price,
                commission=0.0,
            )
        return None
