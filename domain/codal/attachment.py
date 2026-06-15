from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.common.base_entity import BaseEntity


@dataclass
class Attachment(BaseEntity):
    disclosure_id: str
    file_name: str
    file_url: str = ""
    file_size: int = 0
    file_type: str = ""
    description: str = ""

    def __init__(
        self,
        id: str,
        disclosure_id: str,
        file_name: str,
        file_url: str = "",
        file_size: int = 0,
        file_type: str = "",
        description: str = "",
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.disclosure_id = disclosure_id
        self.file_name = file_name
        self.file_url = file_url
        self.file_size = file_size
        self.file_type = file_type
        self.description = description
