from __future__ import annotations

import asyncio
import functools
import random
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from core.logging import get_logger

F = TypeVar("F", bound=Callable[..., Any])
T = TypeVar("T")

logger = get_logger(__name__)


class RetryPolicy:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions

    def get_delay(self, attempt: int) -> float:
        delay = min(self.base_delay * (self.backoff_factor**attempt), self.max_delay)
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        return delay

    async def execute(self, coro_factory: Callable[[], Coroutine[Any, Any, T]], context: str = "") -> T:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await coro_factory()
            except self.retryable_exceptions as e:
                last_exc = e
                if attempt < self.max_retries:
                    delay = self.get_delay(attempt)
                    logger.warning(
                        "Retry attempt %d/%d failed for %s: %s. Retrying in %.2fs",
                        attempt,
                        self.max_retries,
                        context or coro_factory.__name__,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "All %d retries failed for %s: %s",
                        self.max_retries,
                        context or coro_factory.__name__,
                        e,
                    )
        raise last_exc  # type: ignore[misc]


def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
) -> Callable[[F], F]:
    policy = RetryPolicy(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        backoff_factor=backoff_factor,
        jitter=jitter,
    )

    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await policy.execute(lambda: func(*args, **kwargs), context=func.__name__)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            import time

            last_exc: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < max_retries:
                        delay = base_delay * (backoff_factor ** (attempt - 1))
                        if jitter:
                            delay *= 0.5 + random.random() * 0.5
                        time.sleep(min(delay, max_delay))
            raise last_exc  # type: ignore[misc]

        return sync_wrapper  # type: ignore[return-value]

    return decorator
