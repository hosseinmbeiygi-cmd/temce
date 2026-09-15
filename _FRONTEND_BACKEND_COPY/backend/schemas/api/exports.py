from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    dataset: str = "quotes"
    format: str = "csv"
    filters: dict[str, Any] = Field(default_factory=dict)
    symbol: str = ""
    start_date: str = ""
    end_date: str = ""


class ExportResponse(BaseModel):
    id: str
    dataset: str = ""
    format: str = ""
    status: str = "pending"
    file_url: str = ""
    file_size_bytes: int = 0
    record_count: int = 0
    created_at: str = ""
    expires_at: str = ""


class ExportListResponse(BaseModel):
    items: list[ExportResponse] = Field(default_factory=list)
    total: int = 0
