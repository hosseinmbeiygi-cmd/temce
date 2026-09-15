from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backtesting.types import BacktestResult, FillEvent, OrderEvent


class Strategy(ABC):
    @abstractmethod
    async def on_bar(self, data: dict[str, Any]) -> list[OrderEvent]: ...

    @abstractmethod
    async def on_tick(self, data: dict[str, Any]) -> list[OrderEvent]: ...

    @abstractmethod
    def reset(self) -> None: ...


class BrokerSimulator(ABC):
    @abstractmethod
    async def submit_order(self, order: OrderEvent) -> FillEvent | None: ...

    @abstractmethod
    async def get_positions(self) -> dict[str, Any]: ...

    @abstractmethod
    async def get_cash(self) -> float: ...


class PortfolioModel(ABC):
    @abstractmethod
    async def update_fill(self, fill: FillEvent) -> None: ...

    @abstractmethod
    async def mark_to_market(self, prices: dict[str, float]) -> None: ...

    @abstractmethod
    async def get_nav(self) -> float: ...


class MetricEvaluator(ABC):
    @abstractmethod
    def compute(self, result: BacktestResult) -> dict[str, float]: ...

    @abstractmethod
    def get_metric_names(self) -> list[str]: ...
