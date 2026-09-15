from __future__ import annotations

from core.exceptions import AppError


class RateLimitError(AppError):
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int | None = None) -> None:
        super().__init__(message=message, code="RATE_LIMIT", details={"retry_after": retry_after})


class BudgetExhaustedError(RateLimitError):
    def __init__(self, message: str = "Rate limit budget exhausted", reset_time: float | None = None) -> None:
        super().__init__(message=message, retry_after=int(reset_time) if reset_time else None)


class TokenBucketEmptyError(RateLimitError):
    def __init__(self, message: str = "Token bucket empty", wait_time: float | None = None) -> None:
        super().__init__(message=message, retry_after=int(wait_time) if wait_time else None)


class ConcurrencyLimitError(RateLimitError):
    def __init__(self, message: str = "Concurrency limit reached", max_concurrent: int | None = None) -> None:
        super().__init__(message=message, retry_after=None)
