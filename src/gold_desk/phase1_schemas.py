"""Phase 1 contract — GoldDesk entry-data terminal (no OMS).

All monetary values are **Rial** unless a field name says otherwise. Phase 0
still exposes Toman; Phase 1 is deliberately explicit so a Toman value can
never be labelled Rial by accident.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field

Phase1Quality = Literal["LIVE", "DELAYED", "SAMPLE", "EDUCATIONAL", "NO_DATA"]


class TerminalCapabilities(BaseModel):
    """Hard-coded capability statement — Phase 1 has no order surface."""

    orders: bool = False
    wallet: bool = False
    delivery: bool = False
    preview_only: bool = True


class TerminalReferences(BaseModel):
    xau_usd: float | None = None
    usd_irt_rial: float | None = None
    as_of: datetime | None = None
    source: str = "brsapi"
    quality: Phase1Quality = "NO_DATA"
    unit: Literal["rial"] = "rial"
    data_gaps: list[str] = Field(default_factory=list)


class TickerItem(BaseModel):
    key: str
    label: str
    price: float | None = None
    unit: Literal["ounce", "rial"]
    change_pct: float | None = None
    change_amount: float | None = None
    as_of: datetime | None = None
    source: str = "brsapi"
    source_detail: str
    quality: Phase1Quality = "NO_DATA"
    status: Literal["ok", "no_data", "under_construction"] = "ok"
    note: str | None = None


class PhysicalRow(BaseModel):
    symbol: str
    label: str
    kind: Literal["gold", "coin"]
    price_basis: Literal["gram", "mesghal", "coin"]
    price: float | None = None
    change_pct: float | None = None
    change_amount: float | None = None
    intrinsic: float | None = None
    bubble_pct: float | None = None
    bubble_amount: float | None = None
    implied_usd: float | None = None
    as_of: datetime | None = None
    source: str = "brsapi"
    source_detail: str = "brsapi_gold_coin_prices"
    quality: Phase1Quality = "NO_DATA"
    intrinsic_quality: Phase1Quality = "NO_DATA"
    data_gaps: list[str] = Field(default_factory=list)


class FundComposition(BaseModel):
    coin_pct: float | None = None
    bar_pct: float | None = None
    cash_pct: float | None = None
    other_pct: float | None = None
    as_of: datetime | None = None
    source: str | None = None


class FundRow(BaseModel):
    symbol: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    change_amount: float | None = None
    last_trade_date: str | None = None
    last_trade_time: str | None = None
    volume: int | None = None
    turnover: float | None = None
    market_cap: float | None = None
    nav: float | None = None
    nav_issue: float | None = None
    nav_redemption: float | None = None
    nav_date: str | None = None
    nav_time: str | None = None
    nav_as_of: datetime | None = None
    nav_source: str = "brsapi_nav_records"
    intrinsic_price: float | None = None
    bubble_nominal_pct: float | None = None
    bubble_nominal_amount: float | None = None
    bubble_intrinsic_pct: float | None = None
    bubble_intrinsic_amount: float | None = None
    bubble_real_pct: float | None = None
    composition: FundComposition | None = None
    composition_status: Literal["available", "needs_composition"] = "needs_composition"
    implied_usd: float | None = None
    as_of: datetime | None = None
    source: str = "brsapi"
    source_detail: str = "brsapi_ime_funds"
    quality: Phase1Quality = "NO_DATA"
    nav_quality: Phase1Quality = "NO_DATA"
    data_gaps: list[str] = Field(default_factory=list)


class CertificateRow(BaseModel):
    contract_code: str
    commodity: str | None = None
    description: str | None = None
    price: float | None = None
    change_pct: float | None = None
    change_amount: float | None = None
    volume: int | None = None
    turnover: float | None = None
    contract_size: float | None = None
    contract_size_unit: str | None = None
    intrinsic: float | None = None
    bubble_pct: float | None = None
    bubble_amount: float | None = None
    implied_usd: float | None = None
    as_of: datetime | None = None
    source_date: str | None = None
    source: str = "brsapi"
    source_detail: str = "brsapi_ime_certificates"
    quality: Phase1Quality = "NO_DATA"
    intrinsic_quality: Phase1Quality = "NO_DATA"
    data_gaps: list[str] = Field(default_factory=list)


class TerminalResponse(BaseModel):
    generated_at: datetime
    unit: Literal["rial"] = "rial"
    references: TerminalReferences
    ticker: list[TickerItem]
    physical: list[PhysicalRow]
    funds: list[FundRow]
    certificates: list[CertificateRow]
    capabilities: TerminalCapabilities = Field(default_factory=TerminalCapabilities)


class WhatIfRequest(BaseModel):
    xau_usd: float = Field(
        ...,
        gt=0,
        le=100_000,
        validation_alias=AliasChoices("xau_usd", "xauUsd"),
    )
    usd_irt_rial: float = Field(
        ...,
        gt=0,
        le=1_000_000_000,
        validation_alias=AliasChoices("usd_irt_rial", "usdIrr"),
        description="USD/IRR in Rial (not Toman)",
    )

    model_config = {"populate_by_name": True}


class WhatIfInputs(BaseModel):
    xau_usd: float
    usd_irt_rial: float
    usd_irt_toman: float


class WhatIfPhysicalItem(BaseModel):
    symbol: str
    label: str
    market_price: float | None = None
    base_intrinsic: float | None = None
    preview_intrinsic: float | None = None
    base_bubble_pct: float | None = None
    preview_bubble_pct: float | None = None
    base_bubble_amount: float | None = None
    preview_bubble_amount: float | None = None
    base_implied_usd: float | None = None
    preview_implied_usd: float | None = None
    quality: Phase1Quality = "NO_DATA"
    preview_quality: Phase1Quality = "SAMPLE"
    data_gaps: list[str] = Field(default_factory=list)


class WhatIfFundEffect(BaseModel):
    symbol: str
    name: str
    nav: float | None = None
    market_price: float | None = None
    nominal_bubble_pct_before: float | None = None
    nominal_bubble_pct_after: float | None = None
    real_bubble_pct_before: float | None = None
    real_bubble_pct_after: float | None = None
    implied_usd_before: float | None = None
    implied_usd_after: float | None = None
    data_gaps: list[str] = Field(default_factory=list)


class WhatIfResponse(BaseModel):
    generated_at: datetime
    inputs: WhatIfInputs
    physical: list[WhatIfPhysicalItem]
    funds: list[WhatIfFundEffect]
    capabilities: TerminalCapabilities = Field(default_factory=TerminalCapabilities)
