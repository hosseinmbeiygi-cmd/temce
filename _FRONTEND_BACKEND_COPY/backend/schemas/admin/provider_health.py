from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProviderHealthSchema(BaseModel):
    provider: str
    status: str = "unknown"
    latency_ms: float = 0.0
    last_success: datetime | None = None
    last_failure: datetime | None = None
    consecutive_failures: int = 0
    error_message: str | None = None


class ProviderHealthSummary(BaseModel):
    total_providers: int = 0
    healthy: int = 0
    degraded: int = 0
    down: int = 0
    unknown: int = 0
    details: list[ProviderHealthSchema] = Field(default_factory=list)
