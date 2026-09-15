from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class Incident:
    def __init__(self, component: str, message: str, severity: str = "warning") -> None:
        self.component = component
        self.message = message
        self.severity = severity
        self.timestamp = datetime.now(UTC)
        self.resolved: bool = False
        self.resolved_at: datetime | None = None

    def resolve(self) -> None:
        self.resolved = True
        self.resolved_at = datetime.now(UTC)

    def duration(self) -> timedelta | None:
        if self.resolved_at:
            return self.resolved_at - self.timestamp
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "message": self.message,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class IncidentPolicy:
    def __init__(self) -> None:
        self._incidents: list[Incident] = []
        self._handlers: list[Callable[[Incident], None]] = []

    def on_incident(self, handler: Callable[[Incident], None]) -> None:
        self._handlers.append(handler)

    def report(self, component: str, message: str, severity: str = "warning") -> Incident:
        incident = Incident(component, message, severity)
        self._incidents.append(incident)
        for handler in self._handlers:
            try:
                handler(incident)
            except Exception as e:
                logger.error("Incident handler failed: %s", e)
        logger.warning("Incident reported: [%s] %s - %s", severity, component, message)
        return incident

    def resolve(self, component: str, message: str | None = None) -> None:
        for incident in reversed(self._incidents):
            if incident.component == component and not incident.resolved:
                incident.resolve()
                logger.info("Incident resolved: %s", component)

    def open_incidents(self) -> list[Incident]:
        return [i for i in self._incidents if not i.resolved]

    def recent(self, minutes: int = 60) -> list[Incident]:
        cutoff = datetime.now(UTC) - timedelta(minutes=minutes)
        return [i for i in self._incidents if i.timestamp >= cutoff]
