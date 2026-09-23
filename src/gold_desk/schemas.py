"""Pydantic schemas — API request/response.

اکیداً typed. هیچ dict آزاد.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ── Live Snapshot ──────────────────────────────────────────────────


class ReferenceBlock(BaseModel):
    """مرجع‌های قیمت (XAU, USD, AED)."""

    xau_usd: float
    usd_irt: float
    aed_irt: float
    aed_parity_usd: float
    aed_gap_pct: float
    source: Literal["brsapi", "tgju", "cache"] = "brsapi"
    age_seconds: float = 0.0


class AssetBlock(BaseModel):
    """یک دارایی (طلا یا سکه)."""

    symbol: str
    display_name: str
    asset_type: Literal["gold", "coin", "fx", "fund"]
    market_price: float
    fair_value: float | None
    bubble_abs: float | None
    bubble_pct: float | None
    implied_usd: float | None
    quality_flag: str = "clean"


class FundBlock(BaseModel):
    """یک صندوق طلا."""

    symbol: str
    fund_name: str
    nav_per_unit: float
    market_price: float | None
    bubble_pct: float | None
    bpr: float
    real_buy_value: int
    real_sell_value: int
    net_inflow: int
    nav_change_7d_pct: float | None = None


class ScoreComponents(BaseModel):
    """اجزای امتیاز — هر کدام با دلیل."""

    bubble: int = Field(..., description="حباب سکه امامی (0-20)")
    bubble_reason: str
    nav: int = Field(..., description="P/NAV صندوق (0-18)")
    nav_reason: str
    tsetmc: int = Field(..., description="BPR + Inflow (0-18)")
    tsetmc_reason: str
    technical: int = Field(..., description="XAU RSI (0-15)")
    technical_reason: str
    parity: int = Field(..., description="AED gap (0-15)")
    parity_reason: str
    fund_flow: int = Field(..., description="NAV 7d trend (0-14)")
    fund_flow_reason: str


class ScoreBlock(BaseModel):
    total: int
    decision: Literal["GREEN", "YELLOW", "RED"]
    components: ScoreComponents
    hard_stop_active: bool = False
    hard_stop_reason: str | None = None


class SnapshotResponse(BaseModel):
    snapshot_at: datetime
    references: ReferenceBlock
    gold: dict[str, AssetBlock]
    coins: dict[str, AssetBlock]
    funds: list[FundBlock]
    score: ScoreBlock
    quality_flag: str = "clean"


# ── History ──────────────────────────────────────────────────────


class BubbleHistoryPoint(BaseModel):
    date: str  # YYYY-MM-DD شمسی
    symbol: str
    market_price: float
    fair_value: float
    bubble_pct: float


class ScoreHistoryPoint(BaseModel):
    score_at: datetime
    total: int
    decision: str
    hard_stop_active: bool


# ── DCA ───────────────────────────────────────────────────────────


class DCARequest(BaseModel):
    total_capital_irt: float = Field(..., gt=0)
    risk_profile: Literal["conservative", "balanced", "aggressive"] = "balanced"
    current_score: int = Field(..., ge=0, le=100)
    preferred_vehicle: Literal["etf", "cert", "melted", "coin", "jewelry"] | None = None


class DCATranche(BaseModel):
    tranche: int
    pct: float
    amount_irt: float
    trigger: str
    vehicle: str
    estimated_fee_irt: float


class DCAResponse(BaseModel):
    total_capital_irt: float
    ladder: list[DCATranche]
    recommended_vehicle: str
    total_fee_irt: float
    net_investable_irt: float
    stop_loss_pct: float
    take_profit_pct: float


# ── Alerts ────────────────────────────────────────────────────────


class AlertRuleCreate(BaseModel):
    name: str
    rule_type: str
    symbol: str | None = None
    threshold: float
    channel: Literal["inapp", "telegram", "both"] = "inapp"
    telegram_chat_id: str | None = None
    cooldown_minutes: int = 30
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    threshold: float | None = None
    channel: str | None = None
    telegram_chat_id: str | None = None
    cooldown_minutes: int | None = None
    enabled: bool | None = None


class AlertRuleOut(BaseModel):
    id: int
    name: str
    rule_type: str
    symbol: str | None
    threshold: float
    channel: str
    telegram_chat_id: str | None
    enabled: bool
    cooldown_minutes: int
    last_fired_at: datetime | None
    created_at: datetime


class AlertEventOut(BaseModel):
    id: int
    rule_id: int
    rule_name: str | None
    symbol: str | None
    trigger_value: float | None
    threshold: float | None
    message: str | None
    channel: str
    sent_at: datetime
    read_at: datetime | None


# ── Watchlist ─────────────────────────────────────────────────────


class WatchlistResponse(BaseModel):
    symbols: list[str]
    updated_at: datetime | None


# ── Health ────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    brsapi_ok: bool
    redis_ok: bool
    db_ok: bool
    last_snapshot_at: datetime | None
    scheduler_jobs: int
    telegram_configured: bool
    active_alert_rules: int
    unread_alerts: int
