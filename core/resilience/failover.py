from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class FailoverStrategy:
    def __init__(self) -> None:
        self._providers: list[tuple[str, Callable[[], Coroutine[Any, Any, T]]]] = []
        self._current_index = 0

    def add_provider(self, name: str, provider: Callable[[], Coroutine[Any, Any, T]]) -> None:
        self._providers.append((name, provider))

    async def execute(self) -> T:
        errors: list[tuple[str, Exception]] = []
        for i in range(len(self._providers)):
            idx = (self._current_index + i) % len(self._providers)
            name, provider = self._providers[idx]
            try:
                result = await provider()
                self._current_index = idx
                return result
            except Exception as e:
                logger.warning("Failover provider %s failed: %s", name, e)
                errors.append((name, e))
        raise FailoverAllFailedError(errors)

    def reset(self) -> None:
        self._current_index = 0


class FailoverAllFailedError(Exception):
    def __init__(self, errors: list[tuple[str, Exception]]) -> None:
        self.errors = errors
        msg = "; ".join(f"{name}: {e}" for name, e in errors)
        super().__init__(f"All failover providers failed: {msg}")
