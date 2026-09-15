from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.logging import get_logger
from core.resilience import CircuitBreaker
from core.result import Result
from core.retry import RetryPolicy

logger = get_logger(__name__)


class BaseProvider(ABC):
    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.config = config or {}
        self.retry_policy = RetryPolicy(
            max_retries=self.config.get("max_retries", 3),
            base_delay=self.config.get("retry_base_delay", 1.0),
        )
        self.circuit_breaker = CircuitBreaker(
            name=name,
            failure_threshold=self.config.get("failure_threshold", 5),
            recovery_timeout=self.config.get("recovery_timeout", 30.0),
        )

    @abstractmethod
    async def fetch(self, **kwargs: Any) -> Result[Any]: ...

    @abstractmethod
    async def health(self) -> dict[str, Any]: ...

    async def safe_fetch(self, **kwargs: Any) -> Result[Any]:
        try:
            return await self.circuit_breaker.call(lambda: self.retry_policy.execute(lambda: self.fetch(**kwargs)))
        except Exception as e:
            logger.error("Provider %s failed: %s", self.name, e)
            return Result.fail(str(e))

    def __repr__(self) -> str:
        return f"Provider(name={self.name})"
