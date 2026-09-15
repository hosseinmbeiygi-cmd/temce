from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetryPolicy:
    max_retries: int = 3
    backoff_factor: float = 1.0
    retry_on_exceptions: tuple[Exception, ...] = (Exception,)
    initial_delay: float = 0.0
    max_delay: float = 60.0
    jitter: bool = False

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        if attempt >= self.max_retries:
            return False
        return isinstance(exception, self.retry_on_exceptions)

    def delay_for(self, attempt: int) -> float:
        import random

        delay = self.initial_delay + (self.backoff_factor * (2**attempt))
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay = delay * random.uniform(0.5, 1.5)
        return delay

    def __repr__(self) -> str:
        return f"RetryPolicy(max_retries={self.max_retries}, backoff_factor={self.backoff_factor})"


@dataclass
class TimeoutPolicy:
    timeout_seconds: float = 30.0
    raise_on_timeout: bool = True
    on_timeout_callback: Callable[[str], Any] | None = None

    def __repr__(self) -> str:
        return f"TimeoutPolicy(timeout_seconds={self.timeout_seconds})"


@dataclass
class CompensationPolicy:
    compensation_fn: Callable[[Any, Any], Any] | None = None
    compensate_on_failure: bool = True
    compensate_on_timeout: bool = True
    max_compensation_retries: int = 3

    def should_compensate(self, failed_step: str, error: Exception) -> bool:
        return self.compensate_on_failure

    def __repr__(self) -> str:
        return (
            f"CompensationPolicy(compensate_on_failure={self.compensate_on_failure}, "
            f"max_compensation_retries={self.max_compensation_retries})"
        )


@dataclass
class WorkflowPolicy:
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    compensation: CompensationPolicy = field(default_factory=CompensationPolicy)

    def __repr__(self) -> str:
        return f"WorkflowPolicy(retry={self.retry}, timeout={self.timeout}, compensation={self.compensation})"


default_retry_policy = RetryPolicy()
default_timeout_policy = TimeoutPolicy()
default_compensation_policy = CompensationPolicy()
default_workflow_policy = WorkflowPolicy()
