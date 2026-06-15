from __future__ import annotations

from pydantic import BaseModel


class TradeSnapshot(BaseModel):
    symbol: str = ""
    price: float = 0.0
    volume: int = 0
    value: float = 0.0
    side: str = ""
    timestamp: str = ""
    trade_id: str = ""


class TradeStreamMessage(BaseModel):
    type: str = "trade"
    data: TradeSnapshot
    stream: str = "trades"
