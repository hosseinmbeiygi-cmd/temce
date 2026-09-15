from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ManualDataRequest(BaseModel):
    symbol: str
    data_type: str = "quote"
    payload: dict[str, Any]
    source: str = "manual"
    notes: str = ""


class ManualDataResponse(BaseModel):
    id: str
    symbol: str = ""
    data_type: str = ""
    status: str = "received"
    record_count: int = 0
    message: str = ""
    created_at: str = ""
