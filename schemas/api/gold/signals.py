"""Gold signals + Kill-Switch status."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from schemas.api.legal import LegalDisclaimerMixin


class GoldSignalAction(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"


class GoldSignalTimeframe(StrEnum):
    SCALP = "SCALP"
    INTRADAY = "INTRADAY"
    SWING = "SWING"
    LONG_TERM = "LONG_TERM"


class GoldSignal(BaseModel, LegalDisclaimerMixin):
    """سیگنال استاندارد طلا (طبق schema پرامپت)."""

    timestamp: str
    asset_symbol: str
    market: str = Field(..., description="TSE / IME / PHYSICAL")
    current_price: float
    action: GoldSignalAction
    confidence_score: float = Field(..., ge=0, le=1)
    timeframe: GoldSignalTimeframe
    entry_low: float
    entry_high: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward_ratio: float
    nav_premium_pct: float | None = None
    coin_bubble_pct: float | None = None
    dollar_adjusted_expected_roi: float | None = None
    leverage: int = 1
    liquidation_price: float | None = None
    health_ratio: float | None = None
    risk_level: str = "LOW"
    rationale: str
    kill_switch_status: str = "NORMAL"


class GoldKillSwitchStatus(BaseModel):
    """وضعیت سیستم هشدار بحرانی."""

    status: str = Field(..., description="NORMAL / WARNING / ACTIVE")
    reason: str | None = None
    triggered_at: str | None = None
    active_rules: list[str] = Field(default_factory=list)
    directive: str | None = None
