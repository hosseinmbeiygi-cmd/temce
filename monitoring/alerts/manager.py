from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    title: str
    message: str
    severity: AlertSeverity = AlertSeverity.INFO
    source: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


AlertHandler = Callable[[Alert], None]


class AlertManager:
    def __init__(self) -> None:
        self._handlers: list[AlertHandler] = []

    def register_handler(self, handler: AlertHandler) -> None:
        self._handlers.append(handler)

    async def send(self, alert: Alert) -> None:
        logger.warning("Alert [%s] %s: %s", alert.severity.value, alert.title, alert.message)
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error("Alert handler failed: %s", e)

    async def warning(self, title: str, message: str, **kwargs: Any) -> None:
        await self.send(Alert(title=title, message=message, severity=AlertSeverity.WARNING, **kwargs))

    async def critical(self, title: str, message: str, **kwargs: Any) -> None:
        await self.send(Alert(title=title, message=message, severity=AlertSeverity.CRITICAL, **kwargs))

    async def info(self, title: str, message: str, **kwargs: Any) -> None:
        await self.send(Alert(title=title, message=message, severity=AlertSeverity.INFO, **kwargs))


alert_manager = AlertManager()
