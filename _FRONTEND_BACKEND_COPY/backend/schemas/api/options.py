from __future__ import annotations

from pydantic import BaseModel, Field


class OptionRequest(BaseModel):
    symbol: str = ""
    underlying_symbol: str = ""
    option_type: str = "call"
    strike_price: float = 0.0
    expiry_date: str = ""


class OptionResponse(BaseModel):
    id: str
    symbol: str = ""
    underlying_symbol: str = ""
    option_type: str = ""
    strike_price: float = 0.0
    expiry_date: str = ""
    last_price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    volume: int = 0
    open_interest: int = 0
    implied_volatility: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0


class OptionListResponse(BaseModel):
    items: list[OptionResponse] = Field(default_factory=list)
    total: int = 0
