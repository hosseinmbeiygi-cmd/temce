"""Screener Filter API schemas — dynamic filter criteria with real data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FilterCriterion(BaseModel):
    """A single filter criterion with field, operator, and value."""

    field: str = Field(..., description="Field to filter on, e.g. rsi, pe, volume, price_change_pct")
    operator: str = Field("gte", description="Comparison operator: gte, lte, eq, between, in")
    value: float | str | list[float | str] | None = None
    value_to: float | str | None = Field(None, description="Upper bound for 'between' operator")


class ScreenerFilterRequest(BaseModel):
    """Request body for the dynamic screener filter endpoint."""

    filters: list[FilterCriterion] = Field(default_factory=list, description="List of filter criteria")
    logic: str = Field("and", description="Logic operator: 'and' or 'or'")
    sort_by: str = Field("smc_score", description="Sort column")
    sort_order: str = Field("desc", description="asc or desc")
    limit: int = Field(100, ge=1, le=200)
    market: str | None = Field(None, description="Market filter (e.g. BOURS, FARA)")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="Minimum SMC score")
    include_details: bool = Field(False, description="Include detailed phase scores in response")


class FilteredItem(BaseModel):
    """A single filtered screener result item."""

    symbol: str
    name: str = ""
    market: str = ""
    industry: str = ""
    last_price: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    value: float = 0.0
    smc_score: float = 0.0
    phase: str = "neutral"
    rank: int = 0
    reason: str = ""

    # Real data values (populated from DB/BrsApi)
    pe_ratio: float | None = None
    eps: float | None = None
    market_value: float | None = None
    trade_count: int | None = None
    price_change_value: float | None = None
    price_first: float | None = None
    price_yesterday: float | None = None
    price_min: float | None = None
    price_max: float | None = None

    # Phase scores
    liquidity_score: float | None = None
    power_score: float | None = None
    structure_score: float | None = None
    orderflow_score: float | None = None
    trigger_score: float | None = None

    # V2 advanced analytics
    rsi: float | None = None
    macd_histogram: float | None = None
    bb_pct: float | None = None
    atr_pct: float | None = None
    adx: float | None = None
    trend_direction: str | None = None
    trend_strength: float | None = None
    volatility_regime: str | None = None
    pattern_signal: str | None = None
    pattern_confidence: float | None = None
    technical_score: float | None = None
    momentum_score: float | None = None
    risk_score: float | None = None
    composite_score: float | None = None
    composite_signal: str | None = None
    support_level: float | None = None
    resistance_level: float | None = None
    distance_to_support: float | None = None
    distance_to_resistance: float | None = None
    poc_price: float | None = None
    value_area_high: float | None = None
    value_area_low: float | None = None
    volume_trend: str | None = None

    details: dict[str, Any] = Field(default_factory=dict)


class ScreenerFilterStats(BaseModel):
    """Statistics on filtered results."""

    total: int = 0
    avg_smc: float = 0.0
    avg_liquidity: float = 0.0
    avg_power: float = 0.0
    avg_change_pct: float = 0.0
    high_score_count: int = 0
    phase_distribution: dict[str, int] = Field(default_factory=dict)
    top_industry: str = ""
    top_industry_count: int = 0


class ScreenerFilterResponse(BaseModel):
    """Response for the dynamic screener filter endpoint."""

    items: list[FilteredItem] = Field(default_factory=list)
    total: int = 0
    stats: ScreenerFilterStats = Field(default_factory=ScreenerFilterStats)
    applied_filters: list[FilterCriterion] = Field(default_factory=list)
