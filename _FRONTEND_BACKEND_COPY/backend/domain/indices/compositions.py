from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class IndexComposition(BaseEntity):
    index_id: str
    effective_date: date | None = None
    members: list[dict[str, Any]] = field(default_factory=list)
    total_weight: float = 0.0
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        index_id: str,
        effective_date: date | None = None,
        members: list[dict[str, Any]] | None = None,
        total_weight: float = 0.0,
        description: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.index_id = index_id
        self.effective_date = effective_date
        self.members = members or []
        self.total_weight = total_weight
        self.description = description
        self.extra = extra or {}
