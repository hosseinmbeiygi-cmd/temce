from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.common.base_entity import BaseEntity


@dataclass
class Sector(BaseEntity):
    code: str
    name: str
    parent_code: str = ""
    level: int = 0
    description: str = ""

    def __init__(
        self,
        id: str,
        code: str,
        name: str,
        parent_code: str = "",
        level: int = 0,
        description: str = "",
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.code = code
        self.name = name
        self.parent_code = parent_code
        self.level = level
        self.description = description
