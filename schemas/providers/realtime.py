from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RealtimeSubscription(BaseModel):
    symbols: list[str]
    channels: list[str] = Field(default_factory=lambda: ["quotes"])
    stream_type: str = "websocket"


class RealtimeMessage(BaseModel):
    type: str = "quote"
    symbol: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = ""
    stream: str = ""
