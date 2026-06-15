from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExportFormat(BaseModel):
    format: str = "csv"
    supported: list[str] = Field(default_factory=lambda: ["csv", "xlsx", "json", "parquet"])
    mime_types: dict[str, str] = Field(
        default_factory=lambda: {
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "json": "application/json",
            "parquet": "application/octet-stream",
        }
    )


class ExportConfig(BaseModel):
    dataset: str
    format: str = "csv"
    filters: dict[str, Any] = Field(default_factory=dict)
    columns: list[str] | None = None
    include_header: bool = True
    compression: str | None = None


class ExportResult(BaseModel):
    id: str
    dataset: str = ""
    format: str = ""
    status: str = "completed"
    file_url: str = ""
    file_size_bytes: int = 0
    record_count: int = 0
    created_at: str = ""
    expires_at: str = ""
