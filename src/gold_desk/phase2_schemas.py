"""Phase 2 contract — market coverage (Tehran board, platforms, returns, fund map).

All monetary values are **Rial** unless a field name ends in ``_usd`` or
``base_currency`` says otherwise. Phase 2 is read-only and has no order,
wallet, checkout, or payment surface; :class:`MarketCapabilities` states that
explicitly so a client cannot infer a trading capability that does not exist.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from .phase1_schemas import TerminalReferences

Phase2Quality = Literal["LIVE", "DELAYED", "SAMPLE", "EDUCATIONAL", "NO_DATA"]
SourceStatus = Literal["connected", "partial", "not_connected"]
CoverageStatus = Literal["complete", "incomplete", "no_data"]
PeriodKey = Literal["1m", "3m", "6m", "9m", "1y"]


class MarketCapabilities(BaseModel):
    """Phase 2 has no trading or payment surface."""

    orders: bool = False
    wallet: bool = False
    delivery: bool = False
    checkout: bool = False
    payment: bool = False
    preview_only: bool = True


# ── Tehran shop / banking board ─────────────────────────────────


class TehranRow(BaseModel):
    key: str
    label: str
    kind: Literal["gold", "coin", "used", "exchange"]
    price_basis: Literal["gram", "coin"]
    purity: int | None = None
    tehran_price: float | None = None
    official_symbol: str | None = None
    official_label: str | None = None
    official_price: float | None = None
    spread_vs_official_pct: float | None = None
    spread_vs_official_amount: float | None = None
    change_pct: float | None = None
    change_amount: float | None = None
    intrinsic: float | None = None
    bubble_pct: float | None = None
    bubble_amount: float | None = None
    implied_usd: float | None = None
    as_of: datetime | None = None
    source: str = "not_connected"
    source_detail: str = "tehran_shop_feed"
    quality: Phase2Quality = "NO_DATA"
    intrinsic_quality: Phase2Quality = "NO_DATA"
    note: str | None = None
    data_gaps: list[str] = Field(default_factory=list)


class TehranBoardResponse(BaseModel):
    generated_at: datetime
    unit: Literal["rial"] = "rial"
    references: TerminalReferences
    source_status: SourceStatus = "not_connected"
    rows: list[TehranRow]
    capabilities: MarketCapabilities = Field(default_factory=MarketCapabilities)


# ── Online platforms (price comparison only) ────────────────────


class PlatformQuote(BaseModel):
    platform: str
    platform_slug: str
    buy_price: float | None = None
    sell_price: float | None = None
    low_price: float | None = None
    high_price: float | None = None
    intrinsic_18k: float | None = None
    bubble_pct: float | None = None
    implied_usd: float | None = None
    as_of: datetime | None = None
    source: str
    source_detail: str
    quality: Phase2Quality = "NO_DATA"
    data_gaps: list[str] = Field(default_factory=list)


class PlatformsResponse(BaseModel):
    generated_at: datetime
    unit: Literal["rial"] = "rial"
    source_status: SourceStatus = "not_connected"
    platform_count: int = 0
    rows: list[PlatformQuote] = Field(default_factory=list)
    notice: str
    capabilities: MarketCapabilities = Field(default_factory=MarketCapabilities)


# ── Returns matrix ──────────────────────────────────────────────


class PeriodReturn(BaseModel):
    period: PeriodKey
    value: float | None = None
    status: CoverageStatus = "no_data"
    start_date: date | None = None
    end_date: date | None = None
    start_price: float | None = None
    end_price: float | None = None
    observations: int = 0
    reason: str | None = None


class AssetReturnRow(BaseModel):
    key: str
    label: str
    asset_type: Literal["gold", "currency", "index", "fund_index", "inflation", "crypto"]
    native_currency: Literal["IRR", "USD"]
    returns: dict[PeriodKey, PeriodReturn]
    correlation_90d: float | None = None
    correlation_observations: int = 0
    correlation_status: CoverageStatus = "no_data"
    correlation_reason: str | None = None
    quality: Phase2Quality = "NO_DATA"
    source: str
    data_gaps: list[str] = Field(default_factory=list)


class ReturnsMatrixResponse(BaseModel):
    generated_at: datetime
    base_currency: Literal["IRR", "USD"]
    periods: list[PeriodKey]
    correlation_against: Literal["USD/IRR"] = "USD/IRR"
    method: str
    rows: list[AssetReturnRow]
    capabilities: MarketCapabilities = Field(default_factory=MarketCapabilities)


# ── Fund market map ─────────────────────────────────────────────


class FundMapCell(BaseModel):
    symbol: str
    name: str
    size: float
    size_share_pct: float | None = None
    change_pct: float | None = None
    price: float | None = None
    quality: Phase2Quality = "NO_DATA"
    as_of: datetime | None = None
    href: str
    data_gaps: list[str] = Field(default_factory=list)


class FundMapSummaryItem(BaseModel):
    label: str
    symbol: str | None = None
    value: float
    share_pct: float | None = None


class FundMapSummary(BaseModel):
    total_value: float = 0.0
    currency: Literal["rial"] = "rial"
    size_metric: Literal["trade_value", "market_value"]
    items: list[FundMapSummaryItem] = Field(default_factory=list)
    other_value: float = 0.0
    other_share_pct: float | None = None
    cells_count: int = 0


class FundMapResponse(BaseModel):
    generated_at: datetime
    size_metric: Literal["trade_value", "market_value"] = "trade_value"
    color_scale_pct: float = 4.0
    cells: list[FundMapCell] = Field(default_factory=list)
    summary: FundMapSummary
    capabilities: MarketCapabilities = Field(default_factory=MarketCapabilities)
