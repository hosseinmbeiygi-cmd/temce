from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProviderAuth(BaseModel):
    api_key: str | None = None
    api_secret: str | None = None
    username: str | None = None
    password: str | None = None
    token: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ProviderConfig(BaseModel):
    name: str
    provider_type: str = "tsetmc"
    enabled: bool = True
    base_url: str = ""
    auth: ProviderAuth = Field(default_factory=ProviderAuth)
    timeout_seconds: int = 30
    max_retries: int = 3
    rate_limit_per_minute: int = 60
    params: dict[str, Any] = Field(default_factory=dict)


class ProviderResponse(BaseModel):
    success: bool = True
    data: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    source: str = ""
