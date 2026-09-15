from __future__ import annotations

import asyncio
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class CircuitBreakerState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    async def call(self, func, *args: Any, **kwargs: Any) -> Any:
        import time

        if self.state == CircuitBreakerState.OPEN:
            if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED

    def _on_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            import time

            self.state = CircuitBreakerState.OPEN
            self.last_failure_time = time.monotonic()
            logger.warning("Circuit breaker opened after %d failures", self.failure_count)

    def reset(self) -> None:
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
