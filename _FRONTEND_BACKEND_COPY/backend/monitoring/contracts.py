from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MetricCollector(ABC):
    @abstractmethod
    def record(self, name: str, value: float, tags: dict[str, str] | None = None) -> None: ...

    @abstractmethod
    def get_metrics(self) -> dict[str, Any]: ...


class AlertPublisher(ABC):
    @abstractmethod
    async def publish(self, alert: dict[str, Any]) -> None: ...


class HealthChecker(ABC):
    @abstractmethod
    async def check(self) -> dict[str, Any]: ...


class DriftMonitor(ABC):
    @abstractmethod
    async def detect(self, reference: Any, current: Any) -> dict[str, Any]: ...
