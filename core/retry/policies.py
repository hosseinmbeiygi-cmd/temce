from __future__ import annotations

from core.retry.backoff import BackoffStrategy, ExponentialBackoff


class RetryPolicy:
    def __init__(
        self,
        max_retries: int = 3,
        backoff: BackoffStrategy | None = None,
        retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
        jitter: bool = True,
    ) -> None:
        self.max_retries = max_retries
        self.backoff = backoff or ExponentialBackoff()
        self.retryable_exceptions = retryable_exceptions
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        delay = self.backoff.get_delay(attempt)
        if self.jitter:
            delay *= 0.5 + __import__("random").random() * 0.5
        return delay


class FastRetryPolicy(RetryPolicy):
    def __init__(self) -> None:
        super().__init__(max_retries=2, backoff=ExponentialBackoff(base_delay=0.1, max_delay=2.0))


class DefaultRetryPolicy(RetryPolicy):
    def __init__(self) -> None:
        super().__init__(max_retries=3, backoff=ExponentialBackoff(base_delay=1.0, max_delay=30.0))


class AggressiveRetryPolicy(RetryPolicy):
    def __init__(self) -> None:
        super().__init__(max_retries=5, backoff=ExponentialBackoff(base_delay=0.5, max_delay=60.0))


class NoRetryPolicy(RetryPolicy):
    def __init__(self) -> None:
        super().__init__(max_retries=0)
