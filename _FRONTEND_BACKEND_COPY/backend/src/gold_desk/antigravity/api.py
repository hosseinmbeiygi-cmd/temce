"""Antigravity API — FastAPI router برای سیگنال‌های ساختاریافته.

prefix: /gold/antigravity
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session

from .assets import ETF_ASSETS, PHYSICAL_MARKET
from .calculations import (
    calculate_coin_bubble,
    calculate_dollar_adjusted_return,
    scan_gold_arbitrage,
)
from .kill_switch import evaluate_kill_switch
from .signal_engine import generate_antigravity_signal

router = APIRouter(prefix="/antigravity", tags=["GoldDesk-Antigravity"])


class AntigravitySignalRequest(BaseModel):
    etf_name: str = Field(..., description="زرافشان | لوتوس | گوهر | ثامان")
    market_price: float = Field(..., gt=0)
    nav: float = Field(..., gt=0)
    coin_price_irr: float = Field(..., gt=0)
    gold_oz_usd: float = Field(..., gt=0)
    usd_rate: float = Field(..., gt=0)
    etf_price_per_gram: float | None = None
    physical_gold_price_per_gram: float | None = None
    entry_value_irr: float | None = None
    entry_usd_rate: float | None = None
    leverage: int = Field(1, ge=1, le=20)
    position_type: Literal["LONG", "SHORT"] = "LONG"
    equity: float | None = None


@router.post("/signal", summary="Generate Antigravity structured signal")
async def post_signal(req: AntigravitySignalRequest) -> dict:
    """تولید سیگنال ساختاریافته طبق Output Schema استاندارد."""
    sig = generate_antigravity_signal(
        etf_name=req.etf_name,
        market_price=req.market_price,
        nav=req.nav,
        coin_price_irr=req.coin_price_irr,
        gold_oz_usd=req.gold_oz_usd,
        usd_rate=req.usd_rate,
        etf_price_per_gram=req.etf_price_per_gram,
        physical_gold_price_per_gram=req.physical_gold_price_per_gram,
        entry_value_irr=req.entry_value_irr,
        entry_usd_rate=req.entry_usd_rate,
        leverage=req.leverage,
        position_type=req.position_type,
        equity=req.equity,
    )
    return {"success": True, "data": sig.model_dump(mode="json")}


@router.get("/assets", summary="List all Antigravity assets registry")
async def list_assets() -> dict:
    return {
        "success": True,
        "data": {
            "etf_assets": ETF_ASSETS,
            "physical_market": PHYSICAL_MARKET,
        },
    }


@router.get("/quick-signal", summary="Quick signal from live snapshot (no params)")
async def quick_signal(
    etf_name: str = Query("زرافشان"),
    leverage: int = Query(1, ge=1, le=20),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """سیگنال سریع با داده‌های live snapshot فعلی."""
    from ..snapshot_service import _read_brsapi_prices

    prices = await _read_brsapi_prices()
    xau = prices.get("XAUUSD") or 2000
    usd = prices.get("USD") or 70000
    # تخمین بازار ETF از NAV (در حالت live باید از برآپی خوانده شود)
    # fallback: از snapshot_service
    try:
        from ..snapshot_service import build_snapshot

        snap = await build_snapshot(session)
        # پیدا کردن NAV نزدیک‌ترین صندوق
        nav_val = 3500
        mkt_val = 3600
        if snap.funds:
            f = snap.funds[0]
            nav_val = f.nav_per_unit
            mkt_val = f.market_price
        coin_price = 400_000_000  # fallback
        if snap.coins.get("coin_emami"):
            coin_price = snap.coins["coin_emami"].market_price
        sig = generate_antigravity_signal(
            etf_name=etf_name,
            market_price=mkt_val,
            nav=nav_val,
            coin_price_irr=coin_price,
            gold_oz_usd=xau,
            usd_rate=usd,
            leverage=leverage,
        )
        return {"success": True, "data": sig.model_dump(mode="json"), "source": snap.references.source}
    except Exception as exc:
        return {"success": False, "error": {"message": str(exc)}}


@router.post("/kill-switch/check", summary="Evaluate Kill-Switch status")
async def check_kill_switch(
    ounce_change_2h_pct: float | None = None,
    usd_change_2h_pct: float | None = None,
    margin_increased: bool = False,
    market_frozen: bool = False,
) -> dict:
    ks = evaluate_kill_switch(
        ounce_change_2h_pct=ounce_change_2h_pct,
        usd_change_2h_pct=usd_change_2h_pct,
        margin_increased=margin_increased,
        market_frozen=market_frozen,
    )
    return {
        "success": True,
        "data": {
            "status": ks.status,
            "directive": ks.directive,
            "triggered_rules": ks.triggered_rules,
            "matched_keywords": ks.matched_keywords,
            "reason": ks.reason,
        },
    }


@router.post("/arbitrage/scan", summary="Scan gold arbitrage")
async def arbitrage_scan(
    etf_price_per_gram: float = Query(..., gt=0),
    physical_gold_price_per_gram: float = Query(..., gt=0),
    transaction_cost_pct: float = Query(0.003, ge=0, le=0.1),
) -> dict:
    res = scan_gold_arbitrage(etf_price_per_gram, physical_gold_price_per_gram, transaction_cost_pct)
    return {"success": True, "data": res.__dict__}


@router.post("/dollar-return", summary="Calculate dollar-adjusted return")
async def dollar_return(
    entry_value_irr: float = Query(..., gt=0),
    current_value_irr: float = Query(..., gt=0),
    entry_usd_rate: float = Query(..., gt=0),
    current_usd_rate: float = Query(..., gt=0),
) -> dict:
    res = calculate_dollar_adjusted_return(entry_value_irr, current_value_irr, entry_usd_rate, current_usd_rate)
    return {"success": True, "data": res.__dict__}


@router.post("/coin-bubble", summary="Calculate coin bubble")
async def coin_bubble(
    coin_price_irr: float = Query(..., gt=0),
    gold_oz_usd: float = Query(..., gt=0),
    usd_rate: float = Query(..., gt=0),
) -> dict:
    res = calculate_coin_bubble(coin_price_irr, gold_oz_usd, usd_rate)
    return {"success": True, "data": res.__dict__}
