from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Factor(BaseEntity):
    name: str
    category: str = ""
    value: float = 0.0
    weight: float = 1.0
    direction: str = "positive"
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        category: str = "",
        value: float = 0.0,
        weight: float = 1.0,
        direction: str = "positive",
        description: str = "",
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.category = category
        self.value = value
        self.weight = weight
        self.direction = direction
        self.description = description
        self.metadata = metadata or {}

    @property
    def weighted_value(self) -> float:
        return self.value * self.weight

    @property
    def is_positive(self) -> bool:
        return self.direction == "positive"
