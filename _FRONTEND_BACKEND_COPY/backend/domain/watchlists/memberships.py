from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class WatchlistMembership(BaseEntity):
    watchlist_id: str
    user_id: str
    role: str = "viewer"
    is_owner: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        watchlist_id: str,
        user_id: str,
        role: str = "viewer",
        is_owner: bool = False,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.watchlist_id = watchlist_id
        self.user_id = user_id
        self.role = role
        self.is_owner = is_owner
        self.extra = extra or {}
