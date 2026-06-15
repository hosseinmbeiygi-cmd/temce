from __future__ import annotations

from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    report_type: str = "summary"
    symbols: list[str] = Field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    format: str = "pdf"
    include_charts: bool = True


class ReportResponse(BaseModel):
    id: str
    report_type: str = ""
    status: str = "pending"
    file_url: str = ""
    file_size_bytes: int = 0
    created_at: str = ""


class ReportListResponse(BaseModel):
    items: list[ReportResponse] = Field(default_factory=list)
    total: int = 0
