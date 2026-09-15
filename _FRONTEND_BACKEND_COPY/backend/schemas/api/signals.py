from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SignalResponse(BaseModel):
    id: str
    symbol: str = ""
    signal_type: str = ""
    strength: float = 0.0
    direction: str = "neutral"
    source: str = ""
    indicators: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
    generated_at: str = ""
    expires_at: str = ""


class SignalListResponse(BaseModel):
    items: list[SignalResponse] = Field(default_factory=list)
    total: int = 0
