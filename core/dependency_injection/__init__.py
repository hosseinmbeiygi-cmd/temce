from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class Container:
    def __init__(self) -> None:
        self._instances: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}

    def register(self, key: str, instance: Any) -> None:
        self._instances[key] = instance

    def register_factory(self, key: str, factory: Callable[[], Any]) -> None:
        self._factories[key] = factory

    def resolve(self, key: str) -> Any:
        if key in self._instances:
            return self._instances[key]
        if key in self._factories:
            instance = self._factories[key]()
            self._instances[key] = instance
            return instance
        raise KeyError(f"No dependency registered: {key}")

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self.resolve(key)
        except KeyError:
            return default


container = Container()
