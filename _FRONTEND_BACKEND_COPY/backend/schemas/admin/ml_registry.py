from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ModelVersionDetail(BaseModel):
    version: str
    stage: str = "development"
    metrics: dict[str, float] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    artifact_path: str = ""
    created_at: datetime | None = None


class MlModelRegistrySchema(BaseModel):
    id: str
    name: str
    task: str = "classification"
    framework: str = "sklearn"
    latest_version: str = "1.0.0"
    versions: list[ModelVersionDetail] = Field(default_factory=list)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
