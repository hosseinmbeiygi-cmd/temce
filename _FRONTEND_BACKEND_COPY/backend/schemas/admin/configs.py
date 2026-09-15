from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ConfigSchema(BaseModel):
    key: str
    value: Any = None
    description: str = ""
    category: str = "general"
    updated_by: str = "system"
    updated_at: datetime | None = None


class ConfigUpdateRequest(BaseModel):
    value: Any
    description: str | None = None
