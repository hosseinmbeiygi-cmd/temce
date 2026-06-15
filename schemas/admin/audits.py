from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditLogSchema(BaseModel):
    id: str
    action: str
    entity_type: str
    entity_id: str
    actor: str = "system"
    changes: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None
    timestamp: datetime | None = None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogSchema] = Field(default_factory=list)
    total: int = 0
