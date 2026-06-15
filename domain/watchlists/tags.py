from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class WatchlistTag(BaseEntity):
    watchlist_id: str
    tag: str
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        watchlist_id: str,
        tag: str,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.watchlist_id = watchlist_id
        self.tag = tag
        self.extra = extra or {}
