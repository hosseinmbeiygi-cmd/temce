from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ModelRegistryEntry(BaseModel):
    id: str
    name: str
    task: str = "classification"
    framework: str = "sklearn"
    latest_version: str = "1.0.0"
    production_version: str | None = None
    total_versions: int = 1
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ModelRegistryList(BaseModel):
    items: list[ModelRegistryEntry] = Field(default_factory=list)
    total: int = 0
