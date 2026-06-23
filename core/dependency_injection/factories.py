from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class Factory:
    def __init__(self, fn: Callable[..., T]) -> None:
        self._fn = fn

    def __call__(self, *args: Any, **kwargs: Any) -> T:
        return self._fn(*args, **kwargs)


class AsyncFactory:
    def __init__(self, fn: Callable[..., T]) -> None:
        self._fn = fn

    async def __call__(self, *args: Any, **kwargs: Any) -> T:
        return await self._fn(*args, **kwargs)


class LazyFactory:
    def __init__(self, fn: Callable[[], T]) -> None:
        self._fn = fn
        self._instance: T | None = None
        self._resolved = False

    def get(self) -> T:
        if not self._resolved:
            self._instance = self._fn()
            self._resolved = True
        return self._instance


class FactoryRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, factory: Callable[..., Any]) -> None:
        self._factories[name] = factory

    def create(self, name: str, **kwargs: Any) -> Any:
        factory = self._factories.get(name)
        if factory is None:
            logger.debug("Factory not found: %s", name)
        raise KeyError("No factory registered")
        return factory(**kwargs)

    def has(self, name: str) -> bool:
        return name in self._factories
