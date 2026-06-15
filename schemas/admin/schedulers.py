from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SchedulerConfigSchema(BaseModel):
    id: str
    name: str
    job_type: str
    cron_expression: str = "*/5 * * * *"
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    last_run: datetime | None = None
    next_run: datetime | None = None


class SchedulerJobSchema(BaseModel):
    id: str
    name: str
    job_type: str
    status: str = "idle"
    last_run: datetime | None = None
    last_duration_ms: float | None = None
    last_error: str | None = None
    next_run: datetime | None = None
    run_count: int = 0
    fail_count: int = 0
