from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MacroIndicatorRequest(BaseModel):
    indicator: str = "inflation"
    country: str = "iran"
    start_date: str = ""
    end_date: str = ""
    frequency: str = "monthly"


class MacroIndicatorResponse(BaseModel):
    indicator: str = ""
    country: str = ""
    frequency: str = ""
    unit: str = ""
    data: list[dict[str, Any]] = Field(default_factory=list)
    total_records: int = 0
    source: str = ""
    retrieved_at: str = ""
