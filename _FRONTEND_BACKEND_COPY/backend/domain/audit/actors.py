from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class AuditActor(BaseEntity):
    username: str
    display_name: str = ""
    role: str = ""
    email: str = ""
    department: str = ""
    permissions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        username: str,
        display_name: str = "",
        role: str = "",
        email: str = "",
        department: str = "",
        permissions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.username = username
        self.display_name = display_name
        self.role = role
        self.email = email
        self.department = department
        self.permissions = permissions or []
        self.metadata = metadata or {}
