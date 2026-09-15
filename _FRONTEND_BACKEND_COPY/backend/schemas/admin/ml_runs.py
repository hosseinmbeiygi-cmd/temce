from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MlRunSchema(BaseModel):
    id: str
    experiment_name: str = "default"
    run_name: str = ""
    status: str = "running"
    model_type: str = ""
    dataset_snapshot: str = ""
    metrics: dict[str, float] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    error: str | None = None


class MlRunListResponse(BaseModel):
    items: list[MlRunSchema] = Field(default_factory=list)
    total: int = 0
