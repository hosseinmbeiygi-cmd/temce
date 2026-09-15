from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class Incident:
    def __init__(self, provider: str, error: str) -> None:
        self.provider = provider
        self.error = error
        self.timestamp = datetime.now(UTC)
        self.resolved: bool = False
        self.resolved_at: datetime | None = None

    def resolve(self) -> None:
        self.resolved = True
        self.resolved_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class ProviderIncidents:
    def __init__(self) -> None:
        self._incidents: list[Incident] = []

    def report(self, provider: str, error: str) -> Incident:
        incident = Incident(provider, error)
        self._incidents.append(incident)
        logger.error("Incident reported for %s: %s", provider, error)
        return incident

    def resolve(self, incident: Incident) -> None:
        incident.resolve()
        logger.info("Incident resolved for %s", incident.provider)

    def get_active(self) -> list[Incident]:
        return [i for i in self._incidents if not i.resolved]

    def get_by_provider(self, provider: str) -> list[Incident]:
        return [i for i in self._incidents if i.provider == provider]

    def list_all(self) -> list[Incident]:
        return list(self._incidents)
