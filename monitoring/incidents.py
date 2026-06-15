from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class IncidentSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class Incident:
    id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    assigned_to: str | None = None
    resolution_notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class IncidentManager:
    def __init__(self) -> None:
        self._incidents: dict[str, Incident] = {}

    def create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        assigned_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Incident:
        incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
        incident = Incident(
            id=incident_id,
            title=title,
            description=description,
            severity=severity,
            assigned_to=assigned_to,
            metadata=metadata or {},
        )
        self._incidents[incident_id] = incident
        logger.warning(
            "Incident created: %s [%s] - %s",
            incident_id,
            severity.value,
            title,
        )
        return incident

    def resolve_incident(self, incident_id: str, resolution_notes: str = "") -> Incident | None:
        incident = self._incidents.get(incident_id)
        if incident is None:
            logger.error("Incident not found: %s", incident_id)
            return None
        if incident.status == IncidentStatus.RESOLVED:
            logger.warning("Incident already resolved: %s", incident_id)
            return incident
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now(UTC)
        incident.resolution_notes = resolution_notes
        logger.info("Incident resolved: %s", incident_id)
        return incident

    def update_incident_status(self, incident_id: str, status: IncidentStatus) -> Incident | None:
        incident = self._incidents.get(incident_id)
        if incident is None:
            return None
        incident.status = status
        if status == IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.now(UTC)
        logger.info("Incident %s status updated to %s", incident_id, status.value)
        return incident

    def assign_incident(self, incident_id: str, assignee: str) -> Incident | None:
        incident = self._incidents.get(incident_id)
        if incident is None:
            return None
        incident.assigned_to = assignee
        logger.info("Incident %s assigned to %s", incident_id, assignee)
        return incident

    def list_open_incidents(self) -> list[Incident]:
        return [
            inc for inc in self._incidents.values() if inc.status in (IncidentStatus.OPEN, IncidentStatus.IN_PROGRESS)
        ]

    def get_incident_history(self, incident_id: str) -> Incident | None:
        return self._incidents.get(incident_id)

    def get_all_incidents(self) -> list[Incident]:
        return list(self._incidents.values())

    def get_incidents_by_severity(self, severity: IncidentSeverity) -> list[Incident]:
        return [inc for inc in self._incidents.values() if inc.severity == severity]

    def get_incident_metrics(self) -> dict[str, Any]:
        all_incidents = list(self._incidents.values())
        open_count = sum(1 for i in all_incidents if i.status == IncidentStatus.OPEN)
        in_progress_count = sum(1 for i in all_incidents if i.status == IncidentStatus.IN_PROGRESS)
        resolved_count = sum(1 for i in all_incidents if i.status == IncidentStatus.RESOLVED)
        severity_counts = {}
        for sev in IncidentSeverity:
            severity_counts[sev.value] = sum(1 for i in all_incidents if i.severity == sev)
        return {
            "total": len(all_incidents),
            "open": open_count,
            "in_progress": in_progress_count,
            "resolved": resolved_count,
            "by_severity": severity_counts,
        }


incident_manager = IncidentManager()
