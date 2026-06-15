from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    instrument_id: str = ""
    symbol: str = ""
    alert_type: str = "price_above"
    condition: dict[str, Any] = Field(default_factory=dict)
    channels: list[str] = Field(default_factory=lambda: ["console"])
    enabled: bool = True
    description: str = ""


class AlertUpdate(BaseModel):
    condition: dict[str, Any] | None = None
    channels: list[str] | None = None
    enabled: bool | None = None
    description: str | None = None


class AlertResponse(BaseModel):
    id: str
    instrument_id: str = ""
    symbol: str = ""
    alert_type: str = ""
    condition: dict[str, Any] = Field(default_factory=dict)
    channels: list[str] = Field(default_factory=list)
    enabled: bool = True
    triggered_count: int = 0
    last_triggered: datetime | None = None
    description: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AlertListResponse(BaseModel):
    items: list[AlertResponse] = Field(default_factory=list)
    total: int = 0
