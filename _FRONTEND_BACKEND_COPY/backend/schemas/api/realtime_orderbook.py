from __future__ import annotations

from pydantic import BaseModel, Field


class OrderBookLevel(BaseModel):
    price: float = 0.0
    volume: int = 0
    count: int = 0


class OrderBookSnapshot(BaseModel):
    symbol: str = ""
    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)
    timestamp: str = ""
    exchange: str = "tsetmc"
