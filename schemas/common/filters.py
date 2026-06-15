from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class DateRangeFilter(BaseModel):
    start_date: date | None = None
    end_date: date | None = None


class FilterParams(BaseModel):
    search: str | None = Field(default=None, description="Full-text search term")
    is_active: bool | None = None
    date_range: DateRangeFilter | None = None
    tags: list[str] | None = None
    extra_filters: dict[str, Any] | None = None
