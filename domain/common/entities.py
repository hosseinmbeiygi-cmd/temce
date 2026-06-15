from __future__ import annotations

from datetime import datetime

from domain.common.base_entity import BaseEntity


class AggregateRoot(BaseEntity):
    def __init__(self, id: str, created_at: datetime | None = None, updated_at: datetime | None = None) -> None:
        super().__init__(id, created_at, updated_at)
        self._domain_events: list = []

    def record_event(self, event: object) -> None:
        self._domain_events.append(event)

    def clear_events(self) -> list:
        events = list(self._domain_events)
        self._domain_events.clear()
        return events
