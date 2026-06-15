from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class Container:
    def __init__(self) -> None:
        self._instances: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._singletons: dict[str, Any] = {}

    def register(self, key: str, instance: Any) -> None:
        self._instances[key] = instance
        logger.debug("Registered instance: %s", key)

    def register_factory(self, key: str, factory: Callable[[], Any], singleton: bool = True) -> None:
        if singleton:
            self._factories[key] = factory
        else:
            self._factories[key] = factory
        logger.debug("Registered factory: %s (singleton=%s)", key, singleton)

    def resolve(self, key: str) -> Any:
        if key in self._instances:
            return self._instances[key]
        if key in self._singletons:
            return self._singletons[key]
        if key in self._factories:
            instance = self._factories[key]()
            self._singletons[key] = instance
            return instance
        raise KeyError(f"No dependency registered: {key}")

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self.resolve(key)
        except KeyError:
            return default

    def has(self, key: str) -> bool:
        return key in self._instances or key in self._factories or key in self._singletons

    def unregister(self, key: str) -> None:
        self._instances.pop(key, None)
        self._factories.pop(key, None)
        self._singletons.pop(key, None)

    def clear(self) -> None:
        self._instances.clear()
        self._factories.clear()
        self._singletons.clear()
