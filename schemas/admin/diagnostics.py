from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthCheckDetail(BaseModel):
    component: str
    status: str = "healthy"
    latency_ms: float = 0.0
    error: str | None = None
    last_check: datetime | None = None


class DiagnosticsReport(BaseModel):
    id: str
    generated_at: datetime
    summary: str = "All systems operational"
    checks: list[HealthCheckDetail] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
