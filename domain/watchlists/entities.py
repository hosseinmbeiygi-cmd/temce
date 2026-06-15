from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Watchlist(BaseEntity):
    name: str
    owner_id: str = ""
    description: str = ""
    is_public: bool = False
    items_count: int = 0
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        owner_id: str = "",
        description: str = "",
        is_public: bool = False,
        items_count: int = 0,
        tags: list[str] | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.owner_id = owner_id
        self.description = description
        self.is_public = is_public
        self.items_count = items_count
        self.tags = tags or []
        self.extra = extra or {}


@dataclass
class WatchlistItem(BaseEntity):
    watchlist_id: str
    instrument_id: str
    symbol: str = ""
    note: str = ""
    added_by: str = ""
    order: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        watchlist_id: str,
        instrument_id: str,
        symbol: str = "",
        note: str = "",
        added_by: str = "",
        order: int = 0,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.watchlist_id = watchlist_id
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.note = note
        self.added_by = added_by
        self.order = order
        self.extra = extra or {}
