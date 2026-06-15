from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class ScreeningPreset(BaseEntity):
    name: str
    description: str = ""
    filters: list[dict[str, Any]] = field(default_factory=list)
    category: str = ""
    is_public: bool = False
    owner_id: str = ""
    usage_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        description: str = "",
        filters: list[dict[str, Any]] | None = None,
        category: str = "",
        is_public: bool = False,
        owner_id: str = "",
        usage_count: int = 0,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.description = description
        self.filters = filters or []
        self.category = category
        self.is_public = is_public
        self.owner_id = owner_id
        self.usage_count = usage_count
        self.extra = extra or {}
