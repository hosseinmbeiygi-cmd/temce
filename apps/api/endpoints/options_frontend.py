"""Thin frontend-facing options endpoints — wire services to the UI.

- ``GET  /api/options/signals``  → strategy recommendations (signals tab)
- ``POST /api/options/backtest`` → historical backtest report (backtest tab)
- ``POST /api/options/predict``  → expected-move + max-pain forecast (AI tab)

Mounted with prefix ``/api/options`` in ``apps/api/router.py``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from schemas.api.legal import LEGAL_DISCLAIMER_FA
from schemas.common.responses import ApiResponse

router = APIRouter()


class BacktestBody(BaseModel):
    symbol: str = Field(min_length=1)
    strategy: str = "momentum"
    days_to_expiry: int = Field(default=30, ge=1, le=365)
    limit: int = Field(default=500, ge=60, le=2000)


class PredictBody(BaseModel):
    spot: float = Field(gt=0)
    sigma: float = Field(ge=0, le=5)
    days_to_expiry: int = Field(default=30, ge=1, le=365)
    strikes: list[float] = Field(default_factory=list)
    call_oi: list[float] = Field(default_factory=list)
    put_oi: list[float] = Field(default_factory=list)


@router.get("/signals", summary="Option strategy signals")
async def option_signals(
    market_condition: str = "neutral", risk_tolerance: float = 0.5
) -> ApiResponse[dict[str, Any]]:
    from services.options_service import get_options_engine

    engine = get_options_engine()
    signals = engine.recommend(market_condition, risk_tolerance)
    return ApiResponse(success=True, data={
        "signals": signals,
        "legal_disclaimer": LEGAL_DISCLAIMER_FA,
    })


@router.post("/backtest", summary="Backtest an options strategy")
async def option_backtest(body: BacktestBody) -> ApiResponse[dict[str, Any]]:
    from dataclasses import asdict

    from services.options_backtest_service import OptionsBacktestService

    svc = OptionsBacktestService(
        entry_filter=body.strategy, days_to_expiry=body.days_to_expiry
    )
    try:
        bars = await svc.fetch_history(body.symbol, limit=body.limit)
    except RuntimeError as e:
        return ApiResponse(success=False, error={"message": str(e)})
    report = svc.run(bars)
    return ApiResponse(success=True, data={
        "symbol": body.symbol,
        "strategy": body.strategy,
        "metrics": asdict(report.metrics),
        "equity_curve": report.equity_curve,
        "equity_dates": report.equity_dates,
        "trades": [asdict(t) for t in report.trades],
        "legal_disclaimer": LEGAL_DISCLAIMER_FA,
    })


@router.post("/predict", summary="Expected-move + Max Pain forecast")
async def option_predict(body: PredictBody) -> ApiResponse[dict[str, Any]]:
    from dataclasses import asdict

    from services.options_ml_service import OptionsMLService

    svc = OptionsMLService()
    move = svc.expected_move(body.spot, body.sigma, body.days_to_expiry)
    data: dict[str, Any] = {"expected_move": asdict(move)}
    if body.strikes and body.call_oi and body.put_oi:
        data["max_pain"] = asdict(
            svc.max_pain(body.strikes, body.call_oi, body.put_oi)
        )
    data["legal_disclaimer"] = LEGAL_DISCLAIMER_FA
    return ApiResponse(success=True, data=data)
