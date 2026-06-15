from __future__ import annotations

from domain.audit.entities import AuditEntry


def validate_outcome(outcome: str) -> bool:
    return outcome in ("success", "failure", "error")


def validate_severity(severity: str) -> bool:
    return severity in ("info", "warning", "error", "critical")


def is_read_action(entry: AuditEntry) -> bool:
    return entry.action == "read"


def is_write_action(entry: AuditEntry) -> bool:
    return entry.action in ("create", "update", "delete")


def is_critical_action(entry: AuditEntry) -> bool:
    return entry.severity == "critical"
