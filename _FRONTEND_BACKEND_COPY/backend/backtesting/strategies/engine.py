from __future__ import annotations

from abc import ABC, abstractmethod

from backtesting.engine.event_builder import MarketEvent
from backtesting.strategies.context import StrategyContext
from backtesting.types import FillEvent, OrderEvent
from core.logging import get_logger

logger = get_logger(__name__)


class IStrategy(ABC):
    """Standard strategy interface with full lifecycle hooks.

    Lifecycle:
        on_start(ctx) -> called once at simulation start
        on_event(event, ctx) -> called on each market event
        on_fill(fill, ctx) -> called when an order is filled
        on_end(ctx) -> called once at simulation end
    """

    name: str = ""

    @abstractmethod
    def on_start(self, ctx: StrategyContext) -> None: ...

    @abstractmethod
    def on_event(self, event: MarketEvent, ctx: StrategyContext) -> list[OrderEvent]: ...

    def on_fill(self, fill: FillEvent, ctx: StrategyContext) -> None: ...

    def on_end(self, ctx: StrategyContext) -> None: ...


class StrategyEngine:
    """Orchestrates multiple strategies with a shared context.

    Lifecycle:
        set_context → on_start → [on_event → on_fill]* → on_end
    """

    def __init__(self) -> None:
        self._strategies: list[IStrategy] = []
        self._context: StrategyContext | None = None

    def add_strategy(self, strategy: IStrategy) -> None:
        self._strategies.append(strategy)

    def set_context(self, ctx: StrategyContext) -> None:
        self._context = ctx

    @property
    def context(self) -> StrategyContext | None:
        """Public accessor for the shared context."""
        return self._context

    def on_start(self) -> None:
        if self._context is None:
            return
        for strategy in self._strategies:
            try:
                strategy.on_start(self._context)
            except Exception as e:
                logger.error("Strategy %s on_start failed: %s", strategy.name, e)

    def on_event(self, event: MarketEvent) -> list[OrderEvent]:
        if self._context is None:
            return []
        self._context.current_event = event
        all_orders: list[OrderEvent] = []
        for strategy in self._strategies:
            try:
                orders = strategy.on_event(event, self._context)
                all_orders.extend(orders)
            except Exception as e:
                logger.error("Strategy %s on_event failed: %s", strategy.name, e)
        return all_orders

    def notify_fills(self, fills: list[FillEvent]) -> None:
        if self._context is None:
            return
        for fill in fills:
            for strategy in self._strategies:
                try:
                    strategy.on_fill(fill, self._context)
                except Exception as e:
                    logger.error("Strategy %s on_fill failed: %s", strategy.name, e)

    def on_end(self) -> None:
        if self._context is None:
            return
        for strategy in self._strategies:
            try:
                strategy.on_end(self._context)
            except Exception as e:
                logger.error("Strategy %s on_end failed: %s", strategy.name, e)

    @property
    def strategies(self) -> list[IStrategy]:
        return list(self._strategies)

    @property
    def count(self) -> int:
        return len(self._strategies)

    def reset(self) -> None:
        self._context = None
