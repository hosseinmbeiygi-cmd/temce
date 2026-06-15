from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class NewsSource(BaseEntity):
    name: str
    source_type: str = ""
    base_url: str = ""
    feed_url: str = ""
    language: str = "fa"
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        source_type: str = "",
        base_url: str = "",
        feed_url: str = "",
        language: str = "fa",
        is_active: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.source_type = source_type
        self.base_url = base_url
        self.feed_url = feed_url
        self.language = language
        self.is_active = is_active
        self.extra = extra or {}


@dataclass
class NewsCategory(BaseEntity):
    name: str
    slug: str = ""
    description: str = ""
    parent_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        slug: str = "",
        description: str = "",
        parent_id: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.slug = slug
        self.description = description
        self.parent_id = parent_id
        self.extra = extra or {}
