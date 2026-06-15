from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class JobHandler(ABC):
    @abstractmethod
    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class RetryPolicy(ABC):
    @abstractmethod
    def should_retry(self, attempt: int, error: Exception) -> bool: ...

    @abstractmethod
    def backoff_seconds(self, attempt: int) -> float: ...
