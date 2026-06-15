from __future__ import annotations

from typing import Any


class ModelCache:
    def __init__(self, max_size: int = 10) -> None:
        self._cache: dict[str, Any] = {}
        self.max_size = max_size

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, model: Any) -> None:
        if len(self._cache) >= self.max_size:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = model
