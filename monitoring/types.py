from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class AlertEvent:
    alert_id: str
    rule_name: str
    severity: str
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthStatus:
    service: str
    status: str = "healthy"
    checks: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DriftStatus:
    feature: str
    drift_score: float = 0.0
    drifted: bool = False
    p_value: float = 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class JobRunStatus:
    job_name: str
    status: str = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    retry_count: int = 0
