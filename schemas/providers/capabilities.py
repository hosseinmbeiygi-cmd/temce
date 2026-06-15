from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderCapability(BaseModel):
    name: str
    description: str = ""
    supported_instruments: list[str] = Field(default_factory=lambda: ["equity"])
    supported_timeframes: list[str] = Field(default_factory=lambda: ["1d"])
    rate_limit: int = 60
    priority: int = 100


class CapabilitySet(BaseModel):
    provider: str
    capabilities: list[ProviderCapability] = Field(default_factory=list)
    total_capabilities: int = 0
