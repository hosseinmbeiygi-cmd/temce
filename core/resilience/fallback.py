from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class FallbackHandler:
    def __init__(self) -> None:
        self._fallbacks: dict[str, Callable[[], T]] = {}

    def register(self, name: str, fallback: Callable[[], T]) -> None:
        self._fallbacks[name] = fallback

    def execute(self, name: str, primary: Callable[[], T]) -> T:
        try:
            return primary()
        except Exception as e:
            logger.warning("Primary failed for %s: %s. Attempting fallback.", name, e)
            fallback = self._fallbacks.get(name)
            if fallback is None:
                raise
            try:
                return fallback()
            except Exception as fbe:
                logger.error("Fallback also failed for %s: %s", name, fbe)
                raise

    async def execute_async(self, name: str, primary: Callable) -> Any:
        try:
            return await primary()
        except Exception as e:
            logger.warning("Primary async failed for %s: %s. Attempting fallback.", name, e)
            fallback = self._fallbacks.get(name)
            if fallback is None:
                raise
            try:
                return await fallback()
            except Exception as fbe:
                logger.error("Fallback async also failed for %s: %s", name, fbe)
                raise

    def has_fallback(self, name: str) -> bool:
        return name in self._fallbacks
