from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    name: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    aggregate_id: str = ""
    aggregate_type: str = ""
    version: int = 1

    @property
    def event_type(self) -> str:
        return self.__class__.__name__


@dataclass
class EntityCreated(DomainEvent):
    entity_type: str = ""
    entity_id: str = ""


@dataclass
class EntityUpdated(DomainEvent):
    entity_type: str = ""
    entity_id: str = ""
    changes: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityDeleted(DomainEvent):
    entity_type: str = ""
    entity_id: str = ""
