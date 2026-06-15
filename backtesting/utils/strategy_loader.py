from __future__ import annotations

import importlib
import inspect
from typing import Any

from backtesting.strategies.base import BaseStrategy


class StrategyLoader:
    def __init__(self) -> None:
        self._registry: dict[str, type[BaseStrategy]] = {}

    def register(self, name: str, strategy_cls: type[BaseStrategy]) -> None:
        if not issubclass(strategy_cls, BaseStrategy):
            raise TypeError(f"{strategy_cls.__name__} must subclass BaseStrategy")
        self._registry[name] = strategy_cls

    def load(self, name: str, **kwargs: Any) -> BaseStrategy:
        if name in self._registry:
            return self._registry[name](**kwargs)
        try:
            module_path, class_name = name.rsplit(".", 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            if not issubclass(cls, BaseStrategy):
                raise TypeError(f"{class_name} must subclass BaseStrategy")
            self._registry[name] = cls
            return cls(**kwargs)
        except (ImportError, AttributeError, ValueError) as e:
            raise ValueError(f"Could not load strategy '{name}': {e}")

    def discover(self, package: str = "backtesting.strategies") -> dict[str, type[BaseStrategy]]:
        discovered: dict[str, type[BaseStrategy]] = {}
        try:
            module = importlib.import_module(package)
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
                    discovered[name] = obj
                    self._registry[name] = obj
        except ImportError:
            pass
        return discovered

    def list_strategies(self) -> list[str]:
        return list(self._registry.keys())

    def clear(self) -> None:
        self._registry.clear()
