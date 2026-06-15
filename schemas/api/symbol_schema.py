from __future__ import annotations

from pydantic import BaseModel


class SymbolResponse(BaseModel):
    id: str
    symbol: str
    name: str = ""
    isin: str = ""
    market_type: str = ""
    asset_class: str = ""
    status: str = ""
    sector_code: str = ""


class SymbolListResponse(BaseModel):
    items: list[SymbolResponse]
    total: int
    page: int
    page_size: int
