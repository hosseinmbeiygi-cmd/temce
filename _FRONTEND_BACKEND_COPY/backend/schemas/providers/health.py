from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthCheckResult(BaseModel):
    component: str = ""
    status: str = "healthy"
    latency_ms: float = 0.0
    error: str | None = None
    checked_at: str = ""


class ProviderHealthStatus(BaseModel):
    provider: str
    status: str = "unknown"
    last_health_check: datetime | None = None
    last_success: datetime | None = None
    last_failure: datetime | None = None
    consecutive_failures: int = 0
    uptime_pct: float = 100.0
    checks: list[HealthCheckResult] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
