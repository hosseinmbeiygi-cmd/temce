from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProviderConfigSchema(BaseModel):
    name: str
    provider_type: str
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    priority: int = 100
    rate_limit_per_minute: int = 60
    timeout_seconds: int = 30
    retry_count: int = 3


class ProviderTestResult(BaseModel):
    provider: str
    success: bool = False
    latency_ms: float = 0.0
    error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
