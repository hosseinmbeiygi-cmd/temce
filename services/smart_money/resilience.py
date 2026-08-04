"""Resilience Layer — circuit breaker, retry, and fallback for data sources.

Ensures the scoring engine degrades gracefully when BrsApi or other
data sources are unavailable.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class CircuitState(StrEnum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing — reject calls
    HALF_OPEN = "half_open"  # Testing if recovery happened


class CircuitBreaker:
    """Circuit breaker pattern for external service calls.

    States:
    - CLOSED: Normal operation. Failures are counted.
    - OPEN: Too many failures. Calls are rejected immediately.
    - HALF_OPEN: One test call is allowed to check recovery.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            logger.info("Circuit breaker: recovered → CLOSED")
        elif self._state == CircuitState.CLOSED:
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning("Circuit breaker: too many failures → OPEN")

    def allow_request(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        return False

    def get_stats(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "failure_count": self._failure_count,
            "last_failure": self._last_failure_time,
        }


class RetryPolicy:
    """Exponential backoff retry policy."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 10.0,
        backoff_factor: float = 2.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    def get_delay(self, attempt: int) -> float:
        delay = self.base_delay * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay)


class ResilientFetcher:
    """Wraps data fetching with circuit breaker and retry logic.

    Usage:
        fetcher = ResilientFetcher(circuit_breaker, retry_policy)
        data = await fetcher.fetch(brsapi.get_snapshots, limit=200)
    """

    def __init__(
        self,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.retry_policy = retry_policy or RetryPolicy()
        self._fetch_stats = {"attempts": 0, "successes": 0, "failures": 0, "fallbacks": 0}

    async def fetch(
        self,
        primary_fn: Callable,
        fallback_fn: Callable | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Fetch data with circuit breaker, retry, and fallback."""
        self._fetch_stats["attempts"] += 1

        if not self.circuit_breaker.allow_request():
            logger.warning("Circuit breaker OPEN — using fallback")
            self._fetch_stats["fallbacks"] += 1
            if fallback_fn:
                return await fallback_fn(*args, **kwargs) if callable(fallback_fn) else fallback_fn
            return None

        last_error = None
        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                result = await primary_fn(*args, **kwargs) if callable(primary_fn) else primary_fn
                self.circuit_breaker.record_success()
                self._fetch_stats["successes"] += 1
                return result
            except Exception as exc:
                last_error = exc
                self.circuit_breaker.record_failure()
                if attempt < self.retry_policy.max_retries:
                    delay = self.retry_policy.get_delay(attempt)
                    logger.warning("Fetch attempt %d failed: %s — retrying in %.1fs", attempt + 1, exc, delay)
                    time.sleep(delay)

        # All retries failed — try fallback
        self._fetch_stats["failures"] += 1
        self._fetch_stats["fallbacks"] += 1
        logger.error("All retries failed for %s — using fallback", last_error)

        if fallback_fn:
            try:
                return await fallback_fn(*args, **kwargs) if callable(fallback_fn) else fallback_fn
            except Exception as fb_exc:
                logger.error("Fallback also failed: %s", fb_exc)

        return None

    def get_stats(self) -> dict[str, Any]:
        return {**self._fetch_stats, "circuit_breaker": self.circuit_breaker.get_stats()}
