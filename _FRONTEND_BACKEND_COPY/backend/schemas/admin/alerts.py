from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AlertConfigSchema(BaseModel):
    id: str
    name: str
    description: str = ""
    alert_type: str = "threshold"
    config: dict[str, Any] = Field(default_factory=dict)
    channels: list[str] = Field(default_factory=lambda: ["console"])
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AlertListResponse(BaseModel):
    items: list[AlertConfigSchema] = Field(default_factory=list)
    total: int = 0
