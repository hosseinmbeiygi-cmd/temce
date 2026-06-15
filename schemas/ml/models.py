from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ModelVersion(BaseModel):
    version: str = "1.0.0"
    stage: str = "development"
    metrics: dict[str, float] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    feature_count: int = 0
    training_date: str = ""
    dataset_snapshot: str = ""


class ModelArtifact(BaseModel):
    name: str
    artifact_type: str = "model"
    uri: str = ""
    size_bytes: int = 0
    checksum: str = ""


class ModelDefinition(BaseModel):
    id: str
    name: str = ""
    task: str = "classification"
    framework: str = "sklearn"
    description: str = ""
    versions: list[ModelVersion] = Field(default_factory=list)
    artifacts: list[ModelArtifact] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
