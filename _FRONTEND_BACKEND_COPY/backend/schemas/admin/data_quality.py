from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DataQualitySummary(BaseModel):
    dataset: str
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    missing_fields: int = 0
    duplicate_records: int = 0
    completeness_pct: float = 100.0
    last_checked: datetime | None = None


class DataQualityReport(BaseModel):
    id: str
    dataset: str
    summary: DataQualitySummary
    details: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime | None = None
