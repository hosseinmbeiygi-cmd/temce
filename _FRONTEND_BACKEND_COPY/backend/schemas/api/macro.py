from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MacroRequest(BaseModel):
    indicator: str = "inflation"
    country: str = "iran"
    start_date: date | None = None
    end_date: date | None = None


class MacroResponse(BaseModel):
    id: str
    indicator: str = ""
    country: str = ""
    value: float = 0.0
    previous_value: float = 0.0
    change_pct: float = 0.0
    date: str = ""
    source: str = ""
    unit: str = ""
    frequency: str = "monthly"


class MacroListResponse(BaseModel):
    items: list[MacroResponse] = Field(default_factory=list)
    total: int = 0
