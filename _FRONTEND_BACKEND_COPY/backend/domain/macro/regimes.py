from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class MacroRegime(BaseEntity):
    name: str
    regime_type: str = ""
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool = False
    indicators: dict[str, float] = field(default_factory=dict)
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        regime_type: str = "",
        start_date: date | None = None,
        end_date: date | None = None,
        is_active: bool = False,
        indicators: dict[str, float] | None = None,
        description: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.regime_type = regime_type
        self.start_date = start_date
        self.end_date = end_date
        self.is_active = is_active
        self.indicators = indicators or {}
        self.description = description
        self.extra = extra or {}

    def activate(self) -> None:
        self.is_active = True
        self.mark_updated()

    def deactivate(self) -> None:
        self.is_active = False
        self.mark_updated()
