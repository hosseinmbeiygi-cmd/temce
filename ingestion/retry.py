from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import aiohttp

from core.logging import get_logger

T = TypeVar("T")

logger = get_logger(__name__)


async def retry_async(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    max_retries: int = 3,
    backoff_base: float = 2.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple[type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
        ConnectionResetError,
    ),
    **kwargs: Any,
) -> T:
    last_exc: Exception | None = None
    retryable_http_statuses = {408, 425, 429, 500, 502, 503, 504}

    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except aiohttp.ClientResponseError as e:
            # Retrying every 4xx response hides permanent caller errors. Only
            # transient gateway/rate-limit responses are retryable.
            if e.status not in retryable_http_statuses:
                raise
            last_exc = e
            if attempt < max_retries:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                try:
                    delay = float(retry_after) if retry_after is not None else backoff_base**attempt
                except (TypeError, ValueError):
                    delay = backoff_base**attempt
                delay = min(delay + random.uniform(0, 0.5), max_delay)
                logger.warning(
                    "Retry %d/%d after HTTP %s: %.2fs",
                    attempt + 1,
                    max_retries,
                    e.status,
                    delay,
                )
                await asyncio.sleep(delay)
        except retryable_exceptions as e:
            last_exc = e
            if attempt < max_retries:
                delay = min(backoff_base**attempt + random.uniform(0, 0.5), max_delay)
                logger.warning(
                    "Retry %d/%d after %s: %s",
                    attempt + 1,
                    max_retries,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("retry_async exhausted without an exception")  # pragma: no cover



class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        name: str = "default",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self._failures = 0
        self._open = False
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    async def call(
        self,
        fn: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        async with self._lock:
            if self._open:
                if self._last_failure_time is not None and (
                    asyncio.get_event_loop().time() - self._last_failure_time
                    >= self.recovery_timeout
                ):
                    self._open = False
                    self._failures = 0
                else:
                    raise CircuitBreakerOpenError(self.name)

        try:
            result = await fn(*args, **kwargs)
            async with self._lock:
                self._failures = 0
            return result
        except Exception as e:
            async with self._lock:
                self._failures += 1
                self._last_failure_time = asyncio.get_event_loop().time()
                if self._failures >= self.failure_threshold:
                    self._open = True
            raise e


class CircuitBreakerOpenError(Exception):
    def __init__(self, name: str) -> None:
        self.circuit_name = name
        super().__init__(f"Circuit breaker '{name}' is open")
