from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from core.logging import get_logger
from core.retry.backoff import BackoffStrategy, ExponentialBackoff

T = TypeVar("T")
logger = get_logger(__name__)


def is_retryable(exception: Exception, retryable_exceptions: tuple[type[Exception], ...]) -> bool:
    return isinstance(exception, retryable_exceptions)


async def async_retry(
    coro_factory: Callable[[], Coroutine[Any, Any, T]],
    max_retries: int = 3,
    backoff: BackoffStrategy | None = None,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    context: str = "",
) -> T:
    if backoff is None:
        backoff = ExponentialBackoff()
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return await coro_factory()
        except retryable_exceptions as e:
            last_exc = e
            if attempt < max_retries:
                delay = backoff.get_delay(attempt)
                logger.warning("Retry %d/%d failed for %s: %s. Waiting %.2fs", attempt, max_retries, context, e, delay)
                await asyncio.sleep(delay)
    raise last_exc


def sync_retry(
    fn: Callable[[], T],
    max_retries: int = 3,
    backoff: BackoffStrategy | None = None,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    context: str = "",
) -> T:
    import time

    if backoff is None:
        backoff = ExponentialBackoff()
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except retryable_exceptions as e:
            last_exc = e
            if attempt < max_retries:
                delay = backoff.get_delay(attempt)
                logger.warning(
                    "Sync retry %d/%d failed for %s: %s. Waiting %.2fs", attempt, max_retries, context, e, delay
                )
                time.sleep(delay)
    raise last_exc
