from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class MacroSeriesPoint(BaseEntity):
    series_id: str
    value: float = 0.0
    date: date | None = None
    revision: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        series_id: str,
        value: float = 0.0,
        date: date | None = None,
        revision: int = 0,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.series_id = series_id
        self.value = value
        self.date = date
        self.revision = revision
        self.extra = extra or {}
