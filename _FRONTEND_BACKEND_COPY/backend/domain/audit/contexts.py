from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class AuditContext(BaseEntity):
    session_id: str = ""
    request_id: str = ""
    source: str = ""
    environment: str = ""
    correlation_id: str = ""
    tenant_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        session_id: str = "",
        request_id: str = "",
        source: str = "",
        environment: str = "",
        correlation_id: str = "",
        tenant_id: str = "",
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.session_id = session_id
        self.request_id = request_id
        self.source = source
        self.environment = environment
        self.correlation_id = correlation_id
        self.tenant_id = tenant_id
        self.metadata = metadata or {}
