"""Pydantic schemas برای API صندوق‌یار."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .constants import DISCLAIMER_API, DISCLAIMER_PROFILE, DISCLAIMER_UI


# ── پایه ────────────────────────────────────────────────────────────
class SandooghyarBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class FundListItem(SandooghyarBase):
    symbol: str
    name_fa: str
    type_code: str
    type_label_fa: str
    manager: str | None = None
    aum_btoman: Decimal | None = None
    p_nav_ratio: Decimal | None = None
    bubble_pct: Decimal | None = None
    score_total: Decimal | None = None
    signal: str | None = None
    signal_label_fa: str | None = None
    last_updated: datetime | None = None


class FundListResponse(SandooghyarBase):
    items: list[FundListItem]
    total: int
    page: int
    page_size: int
    disclaimer: str = DISCLAIMER_API


# ── پروفایل صندوق ──────────────────────────────────────────────────
class MetricValue(SandooghyarBase):
    """یک سنجه با مقدار، label، و peer percentile."""

    value: Decimal | float | int | str | None = None
    label: str | None = None  # "داده ناکافی" | "مقدار" | ...
    peer_percentile: float | None = None
    is_cold_start: bool = False
    formula: str | None = None
    window_days: int | None = None


class FundMetricsResponse(SandooghyarBase):
    symbol: str
    ts: datetime
    window_days: int
    metrics: dict[str, MetricValue]


class FundHistoryResponse(SandooghyarBase):
    symbol: str
    points: list[dict[str, Any]]


class FundPortfolioResponse(SandooghyarBase):
    symbol: str
    holdings: list[dict[str, Any]]
    report_date: datetime | None = None
    source: str = "codal"


class FundNewsResponse(SandooghyarBase):
    symbol: str
    news: list[dict[str, Any]]


class ReasonVectorItem(SandooghyarBase):
    metric: str
    metric_label_fa: str
    impact: Literal["positive", "negative", "neutral"]
    description_fa: str
    detail_url: str | None = None


class FundRecommendation(SandooghyarBase):
    symbol: str
    score_total: Decimal | None = None
    score_return: Decimal | None = None
    score_risk: Decimal | None = None
    score_cost: Decimal | None = None
    score_liquidity: Decimal | None = None
    signal: str | None = None
    signal_label_fa: str | None = None
    reasons: list[ReasonVectorItem]
    scoring_version: str | None = None
    computed_at: datetime
    is_cold_start_blocked: bool = False
    disclaimer: str = DISCLAIMER_API


class FundProfileResponse(SandooghyarBase):
    symbol: str
    name_fa: str
    type_code: str
    type_label_fa: str
    manager: str | None = None
    custodian: str | None = None
    auditor: str | None = None
    market_maker: str | None = None
    inception_date: datetime | None = None
    is_etf: bool
    recommendation: FundRecommendation
    metrics: FundMetricsResponse | None = None
    disclaimer: str = DISCLAIMER_PROFILE


# ── Screener ────────────────────────────────────────────────────────
class ScreenerFilter(BaseModel):
    field: str
    op: Literal["eq", "gt", "gte", "lt", "lte", "between", "in"] = "gte"
    value: Any
    value2: Any | None = None  # برای between


class ScreenerRequest(BaseModel):
    type_code: str | None = None
    filters: list[ScreenerFilter] = Field(default_factory=list)
    sort_by: str | None = "score_total"
    sort_desc: bool = True
    page: int = 1
    page_size: int = 50


class ScreenerResponse(SandooghyarBase):
    items: list[FundListItem]
    total: int
    page: int
    page_size: int
    disclaimer: str = DISCLAIMER_API


# ── Compare ─────────────────────────────────────────────────────────
class CompareRequest(BaseModel):
    symbols: list[str] = Field(min_length=2, max_length=5)


class CompareResponse(SandooghyarBase):
    funds: list[FundListItem]
    disclaimer: str = DISCLAIMER_API


# ── Bubble Monitor ──────────────────────────────────────────────────
class BubbleLiveItem(SandooghyarBase):
    symbol: str
    nav: Decimal
    market_price: Decimal
    bubble_pct: Decimal
    peer_median_bubble: Decimal | None
    ts: datetime


class BubbleLiveResponse(SandooghyarBase):
    items: list[BubbleLiveItem]
    ts: datetime
    disclaimer: str = DISCLAIMER_API


# ── Health / Sources ────────────────────────────────────────────────
class AdapterHealthItem(SandooghyarBase):
    name: str
    last_success_at: datetime | None
    last_failure_at: datetime | None
    consecutive_failures: int
    circuit_state: str
    total_calls: int
    total_errors: int
    avg_latency_ms: int
    is_stale: bool


class HealthSourcesResponse(SandooghyarBase):
    sources: list[AdapterHealthItem]
    disclaimer: str = DISCLAIMER_UI


# ── Alerts ──────────────────────────────────────────────────────────
class AlertCreate(BaseModel):
    symbol: str | None = None
    event_type: str
    threshold: Any | None = None
    channel: Literal["telegram", "inapp", "email"] = "inapp"


class AlertItem(SandooghyarBase):
    id: int
    user_id: str
    symbol: str | None
    event_type: str
    payload_json: str | None
    created_at: datetime
    delivered_at: datetime | None
    is_read: bool


class AlertListResponse(SandooghyarBase):
    items: list[AlertItem]
    disclaimer: str = DISCLAIMER_UI


# ── Backtest (internal) ─────────────────────────────────────────────
class BacktestReportResponse(SandooghyarBase):
    version: str
    horizons_months: list[int]
    hit_rates: dict[str, float]
    calibration: dict[str, float]
    sample_size: int
    generated_at: datetime
    disclaimer: str = DISCLAIMER_UI


# ── API Error استاندارد ─────────────────────────────────────────────
class ApiError(BaseModel):
    error: str
    message: str
    trace_id: str | None = None
    retry_after: int | None = None
