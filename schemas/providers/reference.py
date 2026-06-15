from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReferenceDataRequest(BaseModel):
    data_type: str = "instruments"
    filters: dict[str, Any] = Field(default_factory=dict)
    page: int = 1
    page_size: int = 100


class ReferenceDataResponse(BaseModel):
    data_type: str = ""
    data: list[dict[str, Any]] = Field(default_factory=list)
    total_records: int = 0
    page: int = 1
    page_size: int = 100
    source: str = ""
