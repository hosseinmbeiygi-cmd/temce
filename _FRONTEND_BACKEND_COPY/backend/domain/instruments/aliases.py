from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class InstrumentAlias(BaseEntity):
    instrument_id: str
    alias: str
    alias_type: str = "symbol"
    source: str = ""
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        alias: str,
        alias_type: str = "symbol",
        source: str = "",
        is_active: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.alias = alias
        self.alias_type = alias_type
        self.source = source
        self.is_active = is_active
        self.extra = extra or {}
