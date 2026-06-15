from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class MacroSeries(BaseEntity):
    name: str
    value: float = 0.0
    unit: str = ""
    date: date | None = None
    frequency: str = "daily"
    source: str = ""
    category: str = ""
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        value: float = 0.0,
        unit: str = "",
        date: date | None = None,
        frequency: str = "daily",
        source: str = "",
        category: str = "",
        description: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.value = value
        self.unit = unit
        self.date = date
        self.frequency = frequency
        self.source = source
        self.category = category
        self.description = description
        self.extra = extra or {}
