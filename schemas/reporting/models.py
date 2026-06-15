from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ReportSchema(BaseModel):
    report_id: str
    title: str
    report_type: str
    format: str = "json"
    data: dict[str, Any] = {}
    generated_at: datetime | None = None


class ExportConfigSchema(BaseModel):
    format: str = "csv"
    include_headers: bool = True
    delimiter: str = ","
    encoding: str = "utf-8"
