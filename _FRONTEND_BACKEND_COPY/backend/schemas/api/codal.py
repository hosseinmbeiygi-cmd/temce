from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class CodalSearchRequest(BaseModel):
    symbol: str = ""
    isin: str = ""
    from_date: date | None = None
    to_date: date | None = None
    report_type: str = ""
    audit_status: str = ""
    page: int = 1
    page_size: int = 50


class CodalReportResponse(BaseModel):
    id: str
    symbol: str = ""
    company_name: str = ""
    isin: str = ""
    report_type: str = ""
    fiscal_year: str = ""
    period: str = ""
    audit_status: str = ""
    publish_date: str = ""
    attachment_url: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class CodalListResponse(BaseModel):
    items: list[CodalReportResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
