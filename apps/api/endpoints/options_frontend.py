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
    # Optional: call/put volume for the PCR gauge.
    call_volume: float = Field(default=0, ge=0)
    put_volume: float = Field(default=0, ge=0)
    # Optional: historical log returns → GARCH realized-vol forecast
    # (when omitted, the caller's IV (``sigma``) is the sole vol input).
    log_returns: list[float] = Field(default_factory=list)
    horizon_days: int = Field(default=30, ge=1, le=365)


@router.get("/signals", summary="Option strategy signals")
async def option_signals(
    market_condition: str = "neutral",
    risk_tolerance: float = 0.5,
    guarded: bool = True,
    iv_rank: float = 50.0,
    min_oi: float = 10.0,
    min_volume: float = 5.0,
    max_spread_pct: float = 10.0,
    underlying: str | None = None,
    ime_commodity: str | None = None,
) -> ApiResponse[dict[str, Any]]:
    from services.options_service import get_options_engine
    from services.options_signals import LiquidityQuote, generate_guarded_signals

    engine = get_options_engine()
    candidates = engine.recommend(market_condition, risk_tolerance)
    quotes: dict[str, LiquidityQuote] | None = None
    liquidity_source = "none"
    if guarded and (underlying or ime_commodity):
        quotes = await _load_chain_quotes(
            underlying=underlying, ime_commodity=ime_commodity
        )
        liquidity_source = "live_chain"
        # Chain-level gate: engine candidates carry strategy ids, not contract
        # symbols, so the guard applies to the underlying's chain as a whole —
        # no liquid leg anywhere → no signal (fail-closed).
        liquid = [q for q in quotes.values() if q.passes(min_oi, min_volume, max_spread_pct)[0]]
        if not liquid:
            return ApiResponse(success=True, data={
                "signals": [],
                "iv_rank": iv_rank,
                "liquidity_source": liquidity_source,
                "liquidity_note": "no liquid chain leg — all signals blocked",
                "legal_disclaimer": LEGAL_DISCLAIMER_FA,
            })
    if guarded:
        signals = generate_guarded_signals(
            candidates, quotes=None, iv_rank_value=iv_rank, min_oi=min_oi,
            min_volume=min_volume, max_spread_pct=max_spread_pct,
        )
        if liquidity_source == "live_chain":
            for s in signals:
                s["liquidity_note"] = "chain liquid — engine-level signal"
                s["liquidity_source"] = "live_chain"
    else:
        signals = candidates
    return ApiResponse(success=True, data={
        "signals": signals,
        "iv_rank": iv_rank,
        "liquidity_source": liquidity_source,
        "legal_disclaimer": LEGAL_DISCLAIMER_FA,
    })


async def _load_chain_quotes(
    underlying: str | None = None, ime_commodity: str | None = None
) -> dict[str, LiquidityQuote]:
    """Build per-symbol liquidity quotes from the live chain tables.

    Stock chains come from ``brsapi_option_snapshots`` (one row per
    contract); IME chains come from ``brsapi_ime_options`` (call/put legs
    share a strike row). Unknown symbols stay absent → fail-closed.
    """
    from sqlalchemy import text

    from core.database import async_session_factory
    from services.options_signals import LiquidityQuote

    out: dict[str, LiquidityQuote] = {}
    if async_session_factory is None:
        return out
    async with async_session_factory() as session:
        if underlying:
            rows = (
                await session.execute(
                    text(
                        "SELECT symbol, open_interest, trade_volume, "
                        "bid_price_1, ask_price_1 FROM brsapi_option_snapshots "
                        "WHERE underlying_symbol = :u"
                    ),
                    {"u": underlying},
                )
            ).fetchall()
            for r in rows:
                if r[0]:
                    out[str(r[0])] = LiquidityQuote(
                        symbol=str(r[0]), open_interest=float(r[1] or 0),
                        volume=float(r[2] or 0), bid=float(r[3] or 0),
                        ask=float(r[4] or 0),
                    )
        elif ime_commodity:
            rows = (
                await session.execute(
                    text(
                        "SELECT call_contract_code, call_open_interest, "
                        "call_trade_volume, call_bid_price_1, call_ask_price_1, "
                        "put_contract_code, put_open_interest, "
                        "put_trade_volume, put_bid_price_1, put_ask_price_1 "
                        "FROM brsapi_ime_options "
                        "WHERE contract_category_commodity = :c "
                        "ORDER BY fetched_at DESC LIMIT 500"
                    ),
                    {"c": ime_commodity},
                )
            ).fetchall()
            for r in rows:
                for base in (0, 5):
                    code = r[base]
                    if code and str(code) not in out:
                        out[str(code)] = LiquidityQuote(
                            symbol=str(code), open_interest=float(r[base + 1] or 0),
                            volume=float(r[base + 2] or 0), bid=float(r[base + 3] or 0),
                            ask=float(r[base + 4] or 0),
                        )
    return out


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


@router.post("/predict", summary="Expected-move + Max Pain + vol forecast")
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
    # Phase 4 surface: PoP / probability-of-touching from full MC paths,
    # PCR sentiment gauge, and optional GARCH realized-vol forecast.
    if body.call_volume > 0 or body.put_volume > 0:
        data["put_call_ratio"] = svc.put_call_ratio(body.call_volume, body.put_volume)
    if body.log_returns:
        data["vol_forecast"] = asdict(
            svc.garch_forecast(body.log_returns, horizon_days=body.horizon_days)
        )
    band = move
    data["probabilities"] = asdict(
        svc.touch_probabilities(
            body.spot,
            body.sigma or (data["vol_forecast"].realized_vol_annual if "vol_forecast" in data else 0.0),
            body.days_to_expiry,
            breakeven_upper=band.upper_68,
            breakeven_lower=band.lower_68,
        )
    )
    data["legal_disclaimer"] = LEGAL_DISCLAIMER_FA
    return ApiResponse(success=True, data=data)
