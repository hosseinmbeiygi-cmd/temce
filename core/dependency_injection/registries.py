from __future__ import annotations

from typing import Any, Generic, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class ServiceRegistry(Generic[T]):
    def __init__(self) -> None:
        self._services: dict[str, T] = {}

    def register(self, key: str, service: T) -> None:
        self._services[key] = service
        logger.debug("Registered service: %s", key)

    def get(self, key: str) -> T:
        service = self._services.get(key)
        if service is None:
            raise KeyError(f"Service not found: {key}")
        return service

    def get_or_default(self, key: str, default: T) -> T:
        return self._services.get(key, default)

    def has(self, key: str) -> bool:
        return key in self._services

    def unregister(self, key: str) -> None:
        self._services.pop(key, None)

    def all(self) -> dict[str, T]:
        return dict(self._services)

    def keys(self) -> list[str]:
        return list(self._services.keys())

    def clear(self) -> None:
        self._services.clear()


class RegistryBuilder:
    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}

    def add(self, key: str, **metadata: Any) -> RegistryBuilder:
        self._entries[key] = metadata
        return self

    def build(self) -> dict[str, dict[str, Any]]:
        return dict(self._entries)

    def remove(self, key: str) -> None:
        self._entries.pop(key, None)
