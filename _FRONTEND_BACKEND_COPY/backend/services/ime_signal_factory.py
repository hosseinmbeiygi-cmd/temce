"""IME signal factory — refinement and issuance per v5.0 architecture doc (§4).

Transforms a pricing candidate into a maturity-graded outcome:
1 (Data Alert) → 2 (Analytical Opportunity) → 3 (Actionable Trade Card).

Hard blocks (§4.2), cost/slippage model (§4.3), scoring (§4.5) and
Fixed Fractional sizing (§5.1) are pure functions; thresholds come from the
central versioned config (config/ime_engine_config.yaml, doc Appendix ه).
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from core.config.ime_engine import load_ime_config

# ── Maturity levels (§4.1) ────────────────────────────────────────────────────


class SignalMaturity(Enum):
    DATA_ALERT = 1
    ANALYTICAL_OPPORTUNITY = 2
    TRADE_CARD = 3


class RejectCode(Enum):
    """Hard-block rejection codes (§4.2)."""

    REJECTED_DATA_STALE = "REJECTED_DATA_STALE"
    REJECTED_DELIVERY_RISK = "REJECTED_DELIVERY_RISK"
    REJECTED_LOW_LIQUIDITY = "REJECTED_LOW_LIQUIDITY"
    REJECTED_TICK_MISMATCH = "REJECTED_TICK_MISMATCH"
    REJECTED_COST_NOT_COVERED = "REJECTED_COST_NOT_COVERED"
    REJECTED_MODEL_LOW_CONFIDENCE = "REJECTED_MODEL_LOW_CONFIDENCE"


class StrategyType(Enum):
    IV_MEAN_REVERSION = "IV_MeanReversion"
    CALENDAR_ARB = "CalendarArb"
    GAMMA_SCALP = "GammaScalp"


# ── Data contracts (§20) ─────────────────────────────────────────────────────


@dataclass
class Leg:
    instrument_key: str
    direction: str  # "Buy" | "Sell"
    quantity: int
    limit_price: float
    execution_order: int


@dataclass
class TradeCard:
    card_id: str
    candidate_id: str
    legs: list[Leg]
    net_edge: float
    signal_score: float
    position_size_suggested: int
    invalidation_point: float | None
    max_loss: float | None
    ttl_seconds: int
    issued_at: datetime
    status: str = "ISSUED"  # ISSUED | EXPIRED | EXECUTED | REJECTED
    rejection_reason: str | None = None


@dataclass
class PricingCandidate:
    """Signal_Candidate (doc §20.2) + the scoring inputs needed downstream (§4.5)."""

    candidate_id: str
    strategy_type: StrategyType
    instrument_keys: list[str]
    theoretical_price: float | None
    market_price: float | None
    mispricing_pct: float | None
    iv: float | None
    greeks: dict[str, float] = field(default_factory=dict)
    model_version: str = ""
    calculation_version: str = ""
    input_data_timestamp: datetime | None = None
    # Scoring inputs (§4.5)
    data_quality: float = 0.0
    liquidity_depth: float = 0.0
    execution_ease: float = 0.0
    model_confidence: float = 0.0


@dataclass
class MarketState:
    """Per-symbol market state consumed by the hard blocks (§4.2) and cost model (§4.3)."""

    snapshot_age_seconds: float = 0.0
    days_to_delivery: float = 0.0
    delivery_capability_checked: bool = False
    visible_volume: int = 0
    min_strategy_volume: int = 0
    tick_size: float = 0.0
    proposed_price: float | None = None
    data_degraded: bool = False
    iv_converged: bool = True
    calibration_rmse: float | None = None
    gross_edge: float = 0.0
    commission: float = 0.0
    market_impact: float = 0.0
    latency_buffer: float = 0.0
    # Almgren-Chriss inputs (§4.3)
    avg_volume: int = 0
    short_term_volatility: float = 0.0
    eta: float = 0.0
    gamma: float = 0.0
    # Sizing inputs (§5.1) — supplied by the caller per instrument
    account_risk_budget: float = 0.0
    stop_loss_distance: float = 0.0


# ── Signal patterns (§4.4) ────────────────────────────────────────────────────


def calendar_arb_ratio(near_futures: float, far_futures: float, carry: float) -> float:
    """(F_near − C_carry) / (F_far − C_carry); signal when < 0.95 (§4.4 / Appendix الف)."""
    if far_futures - carry <= 0:
        return float("inf")
    return (near_futures - carry) / (far_futures - carry)


def iv_mean_reversion_signal(iv_rank: float, iv_to_rv: float, config: dict[str, Any] | None = None) -> bool:
    """Pattern 1: IV_Rank > 80% AND IV/RV(20d) > 1.3 (§4.4)."""
    cfg = config or load_ime_config()
    sf = cfg["signal_factory"]
    return iv_rank > sf["iv_rank_threshold"] and iv_to_rv > sf["iv_to_rv_ratio_threshold"]


# ── Cost & slippage (§4.3) ────────────────────────────────────────────────────


def almgren_chriss_slippage(volume: float, avg_volume: float, volatility: float, eta: float, gamma: float) -> float:
    """ΔP_total = η·σ·√(Q/V) + γ·(Q/V) — simplified Almgren-Chriss impact (§4.3)."""
    if avg_volume <= 0 or volume <= 0:
        return 0.0
    ratio = volume / avg_volume
    return float(eta * volatility * math.sqrt(ratio) + gamma * ratio)


def compute_net_edge(
    gross_edge: float, commission: float, slippage: float, market_impact: float, latency_buffer: float
) -> float:
    """NetEdge = GrossEdge − Commission − Slippage − MarketImpact − LatencyBuffer (§4.3)."""
    return float(gross_edge - commission - slippage - market_impact - latency_buffer)


# ── Hard blocks (§4.2) — evaluated in doc order, first rejection wins ─────────


def evaluate_hard_blocks(
    state: MarketState,
    config: dict[str, Any] | None = None,
    net_edge: float | None = None,
    slippage: float | None = None,
) -> RejectCode | None:
    """Return the first violated hard block, or None when all pass.

    Order per doc §4.2: data staleness → delivery risk → liquidity →
    tick mismatch → model confidence → cost not covered.
    """
    cfg = config or load_ime_config()
    data_cfg = cfg["data"]
    sf_cfg = cfg["signal_factory"]
    sabr_rmse_threshold = cfg["sabr"]["calibration_rmse_threshold"]

    if state.snapshot_age_seconds > data_cfg["staleness_threshold_seconds"]:
        return RejectCode.REJECTED_DATA_STALE
    if state.days_to_delivery < data_cfg["delivery_risk_window_days"] and not state.delivery_capability_checked:
        return RejectCode.REJECTED_DELIVERY_RISK
    effective_volume = state.visible_volume * (1.0 - data_cfg["depth_erosion_factor"])
    if effective_volume < state.min_strategy_volume:
        return RejectCode.REJECTED_LOW_LIQUIDITY
    if state.tick_size > 0 and state.proposed_price is not None:
        ticks = state.proposed_price / state.tick_size
        if abs(ticks - round(ticks)) > 1e-9:
            return RejectCode.REJECTED_TICK_MISMATCH
    if (
        state.data_degraded
        or not state.iv_converged
        or (state.calibration_rmse is not None and state.calibration_rmse >= sabr_rmse_threshold)
    ):
        return RejectCode.REJECTED_MODEL_LOW_CONFIDENCE
    if net_edge is not None and state.gross_edge > 0:
        max_ratio = sf_cfg["slippage_to_gross_edge_max_ratio"]
        slippage_ratio = (slippage if slippage is not None else 0.0) / state.gross_edge
        if slippage_ratio > max_ratio or net_edge <= 0:
            return RejectCode.REJECTED_COST_NOT_COVERED
    return None


# ── Scoring (§4.5) and sizing (§5.1) ──────────────────────────────────────────

SCORE_WEIGHTS = {"data_quality": 0.30, "liquidity_depth": 0.25, "execution_ease": 0.25, "model_confidence": 0.20}


def signal_score(data_quality: float, liquidity_depth: float, execution_ease: float, model_confidence: float) -> float:
    """Signal_Score = 0.30·DQ + 0.25·Liq + 0.25·Exec + 0.20·ModelConf — ranking only (§4.5)."""
    return float(
        SCORE_WEIGHTS["data_quality"] * data_quality
        + SCORE_WEIGHTS["liquidity_depth"] * liquidity_depth
        + SCORE_WEIGHTS["execution_ease"] * execution_ease
        + SCORE_WEIGHTS["model_confidence"] * model_confidence
    )


def score_tier(score: float) -> str:
    """Map score to high/medium/low tier for sizing (§5.1)."""
    if score >= 0.75:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"


# ponytail: tier multipliers are fixed constants; move to config when a second
# product needs different risk budgets.
TIER_MULTIPLIERS = {"high": 1.0, "medium": 0.7, "low": 0.5}


def fixed_fractional_size(account_risk_budget: float, tier: str, stop_loss_distance: float) -> int:
    """Position_Size = (Account_Risk_Budget × Signal_Score_Tier) / Stop_Loss_Distance (§5.1)."""
    if stop_loss_distance <= 0 or account_risk_budget <= 0:
        return 0
    size = account_risk_budget * TIER_MULTIPLIERS.get(tier, 0.5) / stop_loss_distance
    return int(math.floor(size))


# ── Factory pipeline ──────────────────────────────────────────────────────────


def process_candidate(
    candidate: PricingCandidate,
    state: MarketState,
    config: dict[str, Any] | None = None,
    ttl_seconds: int = 20,
) -> tuple[SignalMaturity, RejectCode | None, TradeCard | None]:
    """Run a candidate through the full factory: blocks → cost → score → card.

    Returns (maturity, reject_code, trade_card). A blocked candidate stays at
    DATA_ALERT with the first reject code; a passing one yields TRADE_CARD.
    Appendix A's numeric example is the regression target.

    Raises ``TradingHaltedError`` if the system-wide kill switch is engaged
    (سند §15.3). Existing positions are NOT closed — only new issuance
    stops.
    """
    from services.kill_switch import assert_not_killed

    assert_not_killed()
    cfg = config or load_ime_config()
    slippage = almgren_chriss_slippage(
        state.visible_volume, state.avg_volume, state.short_term_volatility, state.eta, state.gamma
    )
    net_edge = compute_net_edge(state.gross_edge, state.commission, slippage, state.market_impact, state.latency_buffer)

    reject = evaluate_hard_blocks(state, cfg, net_edge=net_edge, slippage=slippage)
    if reject is not None:
        return SignalMaturity.DATA_ALERT, reject, None

    score = signal_score(
        candidate.data_quality, candidate.liquidity_depth, candidate.execution_ease, candidate.model_confidence
    )
    tier = score_tier(score)
    size = fixed_fractional_size(state.account_risk_budget, tier, state.stop_loss_distance)

    card = TradeCard(
        card_id=str(uuid.uuid4()),
        candidate_id=candidate.candidate_id,
        legs=[
            Leg(
                instrument_key=k,
                direction="Buy",
                quantity=1,
                limit_price=state.proposed_price or 0.0,
                execution_order=i,
            )
            for i, k in enumerate(candidate.instrument_keys)
        ],
        net_edge=net_edge,
        signal_score=score,
        position_size_suggested=size,
        invalidation_point=None,
        max_loss=None,
        ttl_seconds=ttl_seconds,
        issued_at=datetime.now(UTC),
    )
    return SignalMaturity.TRADE_CARD, None, card
