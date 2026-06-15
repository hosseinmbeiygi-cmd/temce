from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class ServiceProvider(Generic[T]):
    def __init__(self, service_type: type[T]) -> None:
        self._service_type = service_type
        self._instance: T | None = None

    def get(self) -> T:
        if self._instance is None:
            self._instance = self._create()
        return self._instance

    def _create(self) -> T:
        raise NotImplementedError


class SingletonProvider(Generic[T]):
    def __init__(self, factory: Callable[[], T]) -> None:
        self._factory = factory
        self._instance: T | None = None

    def get(self) -> T:
        if self._instance is None:
            self._instance = self._factory()
        return self._instance

    def reset(self) -> None:
        self._instance = None


class TransientProvider(Generic[T]):
    def __init__(self, factory: Callable[[], T]) -> None:
        self._factory = factory

    def get(self) -> T:
        return self._factory()

    def reset(self) -> None:
        pass


class ScopedProvider(Generic[T]):
    def __init__(self, factory: Callable[[], T]) -> None:
        self._factory = factory
        self._scoped_instances: dict[str, T] = {}

    def get(self, scope_id: str = "default") -> T:
        if scope_id not in self._scoped_instances:
            self._scoped_instances[scope_id] = self._factory()
        return self._scoped_instances[scope_id]

    def clear_scope(self, scope_id: str) -> None:
        self._scoped_instances.pop(scope_id, None)

    def reset(self) -> None:
        self._scoped_instances.clear()
