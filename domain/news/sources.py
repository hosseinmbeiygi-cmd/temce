from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class NewsSourceConfig(BaseEntity):
    source_id: str
    feed_url: str = ""
    update_interval_minutes: int = 30
    max_items_per_fetch: int = 100
    language: str = "fa"
    category: str = ""
    is_active: bool = True
    last_fetched_at: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        source_id: str,
        feed_url: str = "",
        update_interval_minutes: int = 30,
        max_items_per_fetch: int = 100,
        language: str = "fa",
        category: str = "",
        is_active: bool = True,
        last_fetched_at: datetime | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.source_id = source_id
        self.feed_url = feed_url
        self.update_interval_minutes = update_interval_minutes
        self.max_items_per_fetch = max_items_per_fetch
        self.language = language
        self.category = category
        self.is_active = is_active
        self.last_fetched_at = last_fetched_at
        self.extra = extra or {}
