"""Output Schema استاندارد سیگنال Antigravity — دقیقاً طبق پرامپت جامع."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class SignalAsset(BaseModel):
    symbol: str = Field(
        ..., description="ZARFSHANG | LOTUS | GOHAR | SAMAN | IME_GOLD_FUTURES | COIN_PHYSICAL | 18K_GOLD"
    )
    market: str = Field(..., description="TSE | IME | PHYSICAL")
    current_price: float


class SignalAction(BaseModel):
    action: Literal["BUY", "SELL", "HOLD", "CLOSE"]
    confidence_score: float = Field(..., ge=0, le=1)
    timeframe: Literal["SCALP", "INTRADAY", "SWING", "LONG_TERM"]


class TradeParameters(BaseModel):
    entry_range: list[float] = Field(..., min_length=2, max_length=2)
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward_ratio: float


class SignalMetrics(BaseModel):
    nav_premium_pct: float | None = None
    coin_bubble_pct: float | None = None
    gold_usd_correlation: float | None = None
    dollar_adjusted_expected_roi: float | None = None
    # اضافه: برای شفافیت
    gross_spread_pct: float | None = None
    net_spread_pct: float | None = None


class LeverageAndMargin(BaseModel):
    leverage: int = 1
    liquidation_price: float | None = None
    health_ratio: float | None = None
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "EXTREME"] = "LOW"


class AntigravitySignal(BaseModel):
    """خروجی استاندارد سیگنال — همه فیلدها الزامی per spec."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    asset: SignalAsset
    signal: SignalAction
    trade_parameters: TradeParameters
    metrics: SignalMetrics
    leverage_and_margin: LeverageAndMargin
    rationale: str
    kill_switch_status: Literal["NORMAL", "WARNING", "ACTIVE"] = "NORMAL"

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


# ── Helper: محاسبه R/R و سطوح ────────────────────────────────────


def build_trade_parameters(
    entry_mid: float,
    stop_loss: float,
    target_1: float,
    target_2: float,
    spread_pct: float = 0.5,
) -> TradeParameters:
    """ساخت پارامترهای معاملاتی با R/R خودکار."""
    entry_low = entry_mid * (1 - spread_pct / 100)
    entry_high = entry_mid * (1 + spread_pct / 100)
    risk = abs(entry_mid - stop_loss)
    reward = abs(target_1 - entry_mid)
    rr = round(reward / risk, 2) if risk > 0 else 0.0
    return TradeParameters(
        entry_range=[round(entry_low, 0), round(entry_high, 0)],
        stop_loss=round(stop_loss, 0),
        target_1=round(target_1, 0),
        target_2=round(target_2, 0),
        risk_reward_ratio=rr,
    )


def risk_level_from_health(health: float | None, leverage: int) -> str:
    if leverage == 1:
        return "LOW"
    if health is None or health == float("inf"):
        return "LOW"
    if health > 2.0:
        return "LOW"
    if health >= 1.5:
        return "MEDIUM"
    if health >= 1.2:
        return "HIGH"
    return "EXTREME"
