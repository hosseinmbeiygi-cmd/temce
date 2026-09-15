from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class ScreenRun(BaseEntity):
    name: str
    preset_id: str = ""
    filters: list[dict[str, Any]] = field(default_factory=list)
    result_count: int = 0
    status: str = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        preset_id: str = "",
        filters: list[dict[str, Any]] | None = None,
        result_count: int = 0,
        status: str = "pending",
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        parameters: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.preset_id = preset_id
        self.filters = filters or []
        self.result_count = result_count
        self.status = status
        self.started_at = started_at
        self.completed_at = completed_at
        self.parameters = parameters or {}
        self.extra = extra or {}

    def start(self) -> None:
        self.status = "running"
        self.started_at = datetime.now()
        self.mark_updated()

    def complete(self) -> None:
        self.status = "completed"
        self.completed_at = datetime.now()
        self.mark_updated()

    def fail(self) -> None:
        self.status = "failed"
        self.completed_at = datetime.now()
        self.mark_updated()
