from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backtesting.types import OrderEvent


class BaseStrategy(ABC):
    def __init__(self, name: str = "") -> None:
        self.name = name or self.__class__.__name__

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
