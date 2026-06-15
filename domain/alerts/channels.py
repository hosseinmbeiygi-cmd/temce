from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class AlertChannel(BaseEntity):
    name: str
    channel_type: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    is_enabled: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        channel_type: str = "",
        config: dict[str, Any] | None = None,
        is_enabled: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.channel_type = channel_type
        self.config = config or {}
        self.is_enabled = is_enabled
        self.extra = extra or {}

    def enable(self) -> None:
        self.is_enabled = True
        self.mark_updated()

    def disable(self) -> None:
        self.is_enabled = False
        self.mark_updated()


@dataclass
class ChannelConfig:
    endpoint: str = ""
    api_key: str = ""
    recipients: list[str] = field(default_factory=list)
    rate_limit: int = 0
    retry_count: int = 3
    timeout_seconds: int = 10
