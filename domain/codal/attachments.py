from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class CodalAttachment(BaseEntity):
    disclosure_id: str
    file_name: str = ""
    file_url: str = ""
    file_size: int = 0
    mime_type: str = ""
    description: str = ""
    is_downloaded: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        disclosure_id: str,
        file_name: str = "",
        file_url: str = "",
        file_size: int = 0,
        mime_type: str = "",
        description: str = "",
        is_downloaded: bool = False,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.disclosure_id = disclosure_id
        self.file_name = file_name
        self.file_url = file_url
        self.file_size = file_size
        self.mime_type = mime_type
        self.description = description
        self.is_downloaded = is_downloaded
        self.extra = extra or {}

    def mark_downloaded(self) -> None:
        self.is_downloaded = True
        self.mark_updated()
