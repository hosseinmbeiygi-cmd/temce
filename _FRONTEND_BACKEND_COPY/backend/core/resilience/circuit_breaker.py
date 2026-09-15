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
        self._state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0
        self.half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                logger.info("Circuit %s transitioning to half-open", self.name)
        return self._state.value

    @state.setter
    def state(self, value: CircuitState | str) -> None:
        if isinstance(value, str):
            self._state = CircuitState(value)
        else:
            self._state = value

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self._state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def record_success(self) -> None:
        self.failure_count = 0
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED

    def _check_recovery_timeout(self) -> None:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                logger.info("Circuit %s transitioning to half-open", self.name)
                self._state = CircuitState.HALF_OPEN
                self.half_open_calls = 0

    async def call(self, coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
        async with self._lock:
            self._check_recovery_timeout()
            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(f"Circuit {self.name} is open")
            if self._state == CircuitState.HALF_OPEN and self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError(f"Circuit {self.name} half-open limit reached")
        try:
            result = await coro_factory()
        except Exception as e:
            self.record_failure()
            raise e
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("Circuit %s closed after successful probe", self.name)
            else:
                self.failure_count = 0
        return result

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_calls = 0


class CircuitBreakerOpenError(Exception):
    pass


def circuit_breaker(
    name: str = "default",
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    half_open_max_calls: int = 1,
) -> Callable:
    def decorator(func: Callable) -> Callable:
        cb = CircuitBreaker(name, failure_threshold, recovery_timeout, half_open_max_calls)
        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                async def call_func() -> Any:
                    return await func(*args, **kwargs)

                return await cb.call(call_func)

            return async_wrapper
        else:

            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator
