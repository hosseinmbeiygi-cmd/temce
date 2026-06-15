from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from typing import Any, TypeVar

from core.logging import get_logger
from core.retry.policies import DefaultRetryPolicy, RetryPolicy

F = TypeVar("F", bound=Callable[..., Any])
logger = get_logger(__name__)


def retryable(policy: RetryPolicy | None = None) -> Callable[[F], F]:
    if policy is None:
        policy = DefaultRetryPolicy()

    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: Exception | None = None
                for attempt in range(1, policy.max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except policy.retryable_exceptions as e:
                        last_exc = e
                        if attempt < policy.max_retries:
                            delay = policy.get_delay(attempt)
                            logger.warning(
                                "Retry %d/%d for %s: %s. Waiting %.2fs",
                                attempt,
                                policy.max_retries,
                                func.__name__,
                                e,
                                delay,
                            )
                            await asyncio.sleep(delay)
                raise last_exc

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            import time

            last_exc: Exception | None = None
            for attempt in range(1, policy.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except policy.retryable_exceptions as e:
                    last_exc = e
                    if attempt < policy.max_retries:
                        delay = policy.get_delay(attempt)
                        logger.warning(
                            "Sync retry %d/%d for %s: %s. Waiting %.2fs",
                            attempt,
                            policy.max_retries,
                            func.__name__,
                            e,
                            delay,
                        )
                        time.sleep(delay)
            raise last_exc

        return sync_wrapper  # type: ignore[return-value]

    return decorator
