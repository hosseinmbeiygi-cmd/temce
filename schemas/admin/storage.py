from __future__ import annotations

from pydantic import BaseModel, Field


class StorageUsageSchema(BaseModel):
    category: str
    path: str = ""
    file_count: int = 0
    size_bytes: int = 0
    size_mb: float = 0.0


class StorageCleanupRequest(BaseModel):
    categories: list[str] = Field(default_factory=lambda: ["temp", "archives"])
    older_than_days: int = 30
    dry_run: bool = True
