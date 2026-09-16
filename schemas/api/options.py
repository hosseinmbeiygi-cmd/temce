from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class PayoffLegInput(BaseModel):
    type: Literal["call", "put", "stock"] = "call"
    action: Literal["buy", "sell"] = "buy"
    strike: float = Field(0.0, ge=0)
    premium: float = Field(0.0, ge=0)
    quantity: float = Field(1.0, ge=0)


class PayoffPriceRange(BaseModel):
    min: float = Field(0.0, ge=0)
    max: float = Field(1.0, gt=0)
    step: float = Field(1.0, gt=0)


class PayoffCalculatorRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    legs: list[PayoffLegInput] = Field(..., min_length=1, max_length=100)
    price_range: PayoffPriceRange = Field(..., alias="priceRange")
    contract_size: float = Field(
        1000.0,
        alias="contractSize",
        gt=0,
        description="اندازه قرارداد؛ پیش‌فرض ۱۰۰۰ برای قرارداد آپشن بورس تهران",
    )
