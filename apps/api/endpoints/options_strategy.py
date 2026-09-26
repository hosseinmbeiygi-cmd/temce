"""Strategy-engine API surface (spec §7.2-7.11).

Mounted under ``/api/v1/options/strategy`` (see apps/api/router.py).

- ``POST /templates/{name}``       → one-click strategy from the chain (§7.9)
- ``POST /validate``               → pre-trade validation (§7.10)
- ``POST /adjustments``            → roll/defend/hedge suggestions (§7.6)
- ``POST /signal``                 → composite score (§7.3)
- ``POST /size``                   → fixed-fractional / capped Kelly (§7.4)
- ``POST /dual-payoff``            → expiry payoff + current value (§7.2)
- ``POST /lifecycle/{id}/create``  → PROPOSED (§7.7)
- ``POST /lifecycle/{id}/transition`` → audited state machine (§7.7)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from domain.options.signals import PositionSizer, RuleEngine, SignalGenerator
from domain.options.strategy_engine import (
    AdjustmentEngine,
    ChainQuote,
    GreeksAggregator,
    InMemoryChainLookup,
    StrategyLifecycleTracker,
    StrategyStatus,
    StrategyTemplateLibrary,
    StrategyValidator,
    TemplateLeg,
)
from schemas.common.responses import ApiResponse

router = APIRouter(prefix="/strategy")


# ── Request models ────────────────────────────────────────────────────────


class ChainQuoteIn(BaseModel):
    option_type: str = Field(pattern="^(call|put)$")
    strike: float
    expiry: str
    premium: float
    delta: float = 0.0
    open_interest: int = 0
    bid: float | None = None
    ask: float | None = None


class TemplateRequest(BaseModel):
    spot: float = Field(gt=0)
    quotes: list[ChainQuoteIn]
    params: dict[str, Any] = Field(default_factory=dict)


class ValidateLegIn(BaseModel):
    option_type: str
    action: str = Field(pattern="^(buy|sell)$")
    strike: float | None = None
    premium: float = 0.0
    quantity: float = 1.0
    expiry: str | None = None


class ValidateRequest(BaseModel):
    legs: list[ValidateLegIn]
    quotes: list[ChainQuoteIn] = Field(default_factory=list)
    spot: float = 0.0
    portfolio_state: dict[str, Any] = Field(default_factory=dict)
    user_limits: dict[str, Any] = Field(default_factory=dict)
    estimated_margin: float | None = None


class AdjustmentRequest(BaseModel):
    strategy_state: dict[str, Any]
    market_state: dict[str, Any] = Field(default_factory=dict)


class SignalRequest(BaseModel):
    iv_rank: float = Field(ge=0, le=100)
    skew: float = 0.0
    trend_strength: float = 0.0
    term_structure_slope: float = 0.0
    days_to_expiry: int = 30
    ml_probability: float | None = Field(default=None, ge=0, le=1)
    weights: dict[str, float] | None = None


class SizeRequest(BaseModel):
    capital: float = Field(gt=0)
    max_loss_per_contract: float = Field(gt=0)
    method: str = Field(default="fractional_fixed", pattern="^(fractional_fixed|kelly)$")
    risk_per_trade_pct: float = 1.0
    kelly_cap_pct: float = 25.0
    win_rate: float | None = Field(default=None, ge=0, le=1)
    win_loss_ratio: float | None = Field(default=None, gt=0)


class DualPayoffRequest(BaseModel):
    legs: list[ValidateLegIn]
    spot: float = Field(gt=0)
    days_to_expiry: int = Field(ge=0)
    price_min: float = 0.0
    price_max: float = Field(gt=0)
    step: float = Field(gt=0)
    sigma_by_leg: dict[str, float] = Field(default_factory=dict)


class TransitionRequest(BaseModel):
    to_status: str


# ── Helpers ───────────────────────────────────────────────────────────────

_LIFECYCLE = StrategyLifecycleTracker()


def _chain_from(spot: float, quotes: list[ChainQuoteIn]) -> InMemoryChainLookup:
    return InMemoryChainLookup(
        [
            ChainQuote(
                option_type=q.option_type,
                strike=q.strike,
                expiry=q.expiry,
                premium=q.premium,
                delta=q.delta,
                open_interest=q.open_interest,
                bid=q.bid,
                ask=q.ask,
            )
            for q in quotes
        ],
        spot=spot,
    )


def _legs_from(raw: list[ValidateLegIn]) -> list[TemplateLeg]:
    return [
        TemplateLeg(
            option_type=leg.option_type,
            action=leg.action,
            strike=leg.strike,
            premium=leg.premium,
            quantity=leg.quantity,
            expiry=leg.expiry,
        )
        for leg in raw
    ]


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("/templates", summary="Available strategy templates")
async def list_templates() -> ApiResponse[dict[str, Any]]:
    # Templates need a chain; expose names + param hints only.
    lib = StrategyTemplateLibrary(InMemoryChainLookup([], spot=1.0))
    return ApiResponse(success=True, data={"templates": lib.available()})


@router.post("/templates/{name}", summary="Build a strategy with one click (delta-targeted)")
async def build_template(name: str, body: TemplateRequest) -> ApiResponse[dict[str, Any]]:
    try:
        chain = _chain_from(body.spot, body.quotes)
        built = StrategyTemplateLibrary(chain).build(name, **body.params)
    except (ValueError, KeyError) as exc:
        return ApiResponse(success=False, error={"message": str(exc)})
    return ApiResponse(success=True, data=built.as_payload())


@router.post("/validate", summary="Pre-trade validation (liquidity, margin, concentration)")
async def validate(body: ValidateRequest) -> ApiResponse[dict[str, Any]]:
    chain = _chain_from(body.spot, body.quotes) if (body.quotes and body.spot) else None
    errors = StrategyValidator().validate(
        _legs_from(body.legs),
        chain=chain,
        portfolio_state=body.portfolio_state,
        user_limits=body.user_limits,
        estimated_margin=body.estimated_margin,
    )
    return ApiResponse(success=True, data={"errors": errors, "valid": not errors})


@router.post("/adjustments", summary="Roll / defend / delta-hedge suggestions")
async def adjustments(body: AdjustmentRequest) -> ApiResponse[dict[str, Any]]:
    suggestions = AdjustmentEngine().evaluate(body.strategy_state, body.market_state)
    return ApiResponse(success=True, data={"suggestions": suggestions})


@router.post("/signal", summary="Composite signal score (decision support)")
async def signal(body: SignalRequest) -> ApiResponse[dict[str, Any]]:
    generator = SignalGenerator(body.weights)
    result = generator.score(
        {
            "iv_rank": body.iv_rank,
            "skew": body.skew,
            "trend_strength": body.trend_strength,
            "term_structure_slope": body.term_structure_slope,
            "days_to_expiry": body.days_to_expiry,
            "ml_probability": body.ml_probability,
        }
    )
    return ApiResponse(success=True, data=result)


@router.post("/size", summary="Position sizing (fixed-fractional / capped Kelly)")
async def size(body: SizeRequest) -> ApiResponse[dict[str, Any]]:
    try:
        sizer = PositionSizer(
            method=body.method,
            risk_per_trade_pct=body.risk_per_trade_pct,
            kelly_cap_pct=body.kelly_cap_pct,
        )
        result = sizer.size(
            capital=body.capital,
            max_loss_per_contract=body.max_loss_per_contract,
            win_rate=body.win_rate,
            win_loss_ratio=body.win_loss_ratio,
        )
    except ValueError as exc:
        return ApiResponse(success=False, error={"message": str(exc)})
    return ApiResponse(success=True, data=result)


@router.post("/dual-payoff", summary="Expiry payoff + current-value curve (Strategy Builder)")
async def dual_payoff(body: DualPayoffRequest) -> ApiResponse[dict[str, Any]]:
    aggregator = GreeksAggregator()
    try:
        curve = aggregator.dual_payoff_curve(
            _legs_from(body.legs),
            spot=body.spot,
            days_to_expiry=body.days_to_expiry,
            price_min=body.price_min,
            price_max=body.price_max,
            step=body.step,
            sigma_by_leg={int(k): v for k, v in body.sigma_by_leg.items()},
        )
    except ValueError as exc:
        return ApiResponse(success=False, error={"message": str(exc)})
    return ApiResponse(success=True, data={"curve": curve})


@router.post("/lifecycle/{strategy_id}/create", summary="Register a strategy (PROPOSED)")
async def lifecycle_create(strategy_id: str) -> ApiResponse[dict[str, Any]]:
    status = _LIFECYCLE.create(strategy_id)
    return ApiResponse(success=True, data={"strategy_id": strategy_id, "status": status.value})


@router.post("/lifecycle/{strategy_id}/transition", summary="Transition strategy status")
async def lifecycle_transition(strategy_id: str, body: TransitionRequest) -> ApiResponse[dict[str, Any]]:
    try:
        to_status = StrategyStatus(body.to_status)
        status = _LIFECYCLE.transition(strategy_id, to_status)
    except (KeyError, ValueError) as exc:
        return ApiResponse(success=False, error={"message": str(exc)})
    return ApiResponse(success=True, data={"strategy_id": strategy_id, "status": status.value})
