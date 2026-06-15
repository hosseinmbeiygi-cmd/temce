from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DatasetConfig(BaseModel):
    name: str
    description: str = ""
    symbols: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    target: str = "price_change_pct"
    start_date: str = ""
    end_date: str = ""
    train_split_pct: float = 0.8
    val_split_pct: float = 0.1
    test_split_pct: float = 0.1


class DatasetVersion(BaseModel):
    version: str = "1.0.0"
    row_count: int = 0
    column_count: int = 0
    size_bytes: int = 0
    checksum: str = ""
    created_at: str = ""


class DatasetSnapshot(BaseModel):
    id: str
    name: str = ""
    config: DatasetConfig = Field(default_factory=DatasetConfig)
    versions: list[DatasetVersion] = Field(default_factory=list)
    current_version: str = "1.0.0"
    storage_path: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
