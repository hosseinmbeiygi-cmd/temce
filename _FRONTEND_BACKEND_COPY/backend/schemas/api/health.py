from __future__ import annotations

from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    name: str
    status: str = "healthy"
    latency_ms: float = 0.0
    last_check: str = ""
    error: str | None = None


class HealthCheckResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.1.0"
    uptime_seconds: float = 0.0
    components: list[ComponentHealth] = Field(default_factory=list)
    timestamp: str = ""
