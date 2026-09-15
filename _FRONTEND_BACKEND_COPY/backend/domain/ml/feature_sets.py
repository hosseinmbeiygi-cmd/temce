from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class FeatureSet(BaseEntity):
    name: str
    version: str = "1.0"
    features: list[str] = field(default_factory=list)
    description: str = ""
    feature_count: int = 0
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        version: str = "1.0",
        features: list[str] | None = None,
        description: str = "",
        feature_count: int = 0,
        is_active: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.version = version
        self.features = features or []
        self.description = description
        self.feature_count = feature_count or len(self.features)
        self.is_active = is_active
        self.extra = extra or {}
