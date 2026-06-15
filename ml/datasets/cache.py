from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class DatasetCache:
    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, data: Any) -> None:
        self._cache[key] = data
        logger.debug("Cached dataset: %s", key)

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)
        logger.debug("Invalidated cache: %s", key)

    def clear(self) -> None:
        self._cache.clear()
