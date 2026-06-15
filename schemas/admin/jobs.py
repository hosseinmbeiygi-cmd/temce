from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobRunSchema(BaseModel):
    id: str
    job_type: str
    status: str = "pending"
    progress_pct: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    triggered_by: str = "scheduler"


class JobRunListResponse(BaseModel):
    items: list[JobRunSchema] = Field(default_factory=list)
    total: int = 0


class JobTriggerRequest(BaseModel):
    job_type: str
    params: dict[str, Any] = Field(default_factory=dict)
