from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FeatureDefinition(BaseModel):
    name: str
    feature_type: str = "numeric"
    source: str = "quote"
    params: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    dtype: str = "float64"


class FeatureGroup(BaseModel):
    group_name: str
    features: list[FeatureDefinition] = Field(default_factory=list)
    description: str = ""


class FeatureSet(BaseModel):
    name: str
    version: str = "1.0.0"
    groups: list[FeatureGroup] = Field(default_factory=list)
    all_features: list[str] = Field(default_factory=list)
    target: str = ""
    created_at: str = ""
