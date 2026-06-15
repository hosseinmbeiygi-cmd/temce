from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from enum import Enum
from typing import Any, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0
        self.half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(self, coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                    logger.info("Circuit %s transitioning to half-open", self.name)
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    raise CircuitBreakerOpenError(f"Circuit {self.name} is open")

            if self.state == CircuitState.HALF_OPEN and self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError(f"Circuit {self.name} half-open limit reached")

        try:
            result = await coro_factory()
        except Exception as e:
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.monotonic()
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.warning("Circuit %s opened after %d failures", self.name, self.failure_count)
                if self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.OPEN
            raise e

        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("Circuit %s closed after successful probe", self.name)
            else:
                self.failure_count = 0

        return result

    def reset(self) -> None:
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_calls = 0


class CircuitBreakerOpenError(Exception):
    pass
