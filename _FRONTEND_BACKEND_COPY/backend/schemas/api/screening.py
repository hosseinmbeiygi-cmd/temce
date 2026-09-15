from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ScreeningRequest(BaseModel):
    criteria: dict[str, Any] = Field(default_factory=dict)
    market_type: str | None = None
    asset_class: str | None = None
    sector_code: str | None = None
    sort_by: str = "volume"
    sort_order: str = "desc"
    limit: int = 50


class ScreeningResult(BaseModel):
    symbol: str = ""
    name: str = ""
    last_price: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    value: float = 0.0
    market_cap: float = 0.0
    p_e_ratio: float | None = None
    eps: float = 0.0
    sector: str = ""
    match_score: float = 0.0
    matched_criteria: list[str] = Field(default_factory=list)


class ScreeningListResponse(BaseModel):
    items: list[ScreeningResult] = Field(default_factory=list)
    total: int = 0
    criteria_summary: dict[str, Any] = Field(default_factory=dict)
