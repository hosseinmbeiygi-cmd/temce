from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class InstrumentCreate(BaseModel):
    symbol: str
    name: str = ""
    isin: str = ""
    market_type: str = "bours"
    asset_class: str = "equity"
    sector_code: str = ""
    group_code: str = ""
    tick_size: float = 1.0
    lot_size: int = 1
    par_value: int = 1000
    exchange_code: str = ""
    board_code: str = ""


class InstrumentUpdate(BaseModel):
    name: str | None = None
    sector_code: str | None = None
    group_code: str | None = None
    tick_size: float | None = None
    lot_size: int | None = None
    par_value: int | None = None
    eps: float | None = None
    shares_count: int | None = None
    status: str | None = None


class InstrumentResponse(BaseModel):
    id: str
    symbol: str = ""
    name: str = ""
    isin: str = ""
    ins_code: str = ""
    industry_code: str = ""
    market_type: str = ""
    asset_class: str = ""
    status: str = "active"
    sector_code: str = ""
    group_code: str = ""
    sub_group_code: str = ""
    tick_size: float = 0.0
    lot_size: int = 0
    par_value: int = 0
    eps: float = 0.0
    shares_count: int = 0
    base_volume: int = 0
    exchange_code: str = ""
    board_code: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InstrumentListResponse(BaseModel):
    items: list[InstrumentResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
