from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from backtesting.sizing import PositionSizer
from backtesting.types import OrderEvent

if TYPE_CHECKING:
    from backtesting.strategies.context import StrategyContext


class BaseStrategy(ABC):
    def __init__(self, name: str = "", sizing_method: str = "fixed", sizing_value: float = 1000.0) -> None:
        self.name = name or self.__class__.__name__
        self.ctx: StrategyContext | None = None
        self.sizer: PositionSizer = PositionSizer(method=sizing_method, value=sizing_value)

    def set_context(self, ctx: StrategyContext) -> None:
        self.ctx = ctx

    def _compute_quantity(self, price: float, **kwargs: Any) -> int:
        """Compute order quantity using sizer. Falls back to sizer.value/price."""
        if self.ctx:
            qty = self.sizer.calculate(capital=self.ctx.cash, price=price, **kwargs)
        else:
            qty = self.sizer.calculate(capital=0, price=price, **kwargs)
        return max(1, int(qty))

    @abstractmethod
    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]: ...

    def on_tick(self, tick: dict[str, Any]) -> list[OrderEvent]:
        return []

    def on_event(self, event: dict[str, Any]) -> list[OrderEvent]:
        return []

    def reset(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"Strategy(name={self.name})"
