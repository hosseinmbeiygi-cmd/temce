from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class InstrumentGroup(BaseEntity):
    name: str
    group_code: str = ""
    group_type: str = ""
    parent_code: str = ""
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        group_code: str = "",
        group_type: str = "",
        parent_code: str = "",
        description: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.group_code = group_code
        self.group_type = group_type
        self.parent_code = parent_code
        self.description = description
        self.extra = extra or {}
