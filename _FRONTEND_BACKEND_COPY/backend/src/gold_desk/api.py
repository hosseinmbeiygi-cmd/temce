"""FastAPI router — ۸ گروه endpoint.

prefix: /gold (بدون auth چون شخصی است)
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session

from . import dca_planner, snapshot_service
from .alert_engine import seed_default_rules
from .backtest import run_backtest
from .backtest_real import run_real_backtest
from .backtest_runner import run_strategy_backtest
from .black76 import price_option, protective_collar
from .chat import ask_gold_assistant
from .crypto import fetch_crypto_prices, fetch_fx_rates
from .hotpath import build_hotpath_response, get_hot_snapshot
from .live_signals import detect_and_broadcast
from .macro_news import compute_macro_multiplier, fetch_macro_events, scrape_cbi_news
from .metrics import render_prometheus
from .models import AlertEventModel, AlertRuleModel, GoldScoreHistoryModel, GoldSnapshotModel
from .pattern_detector import detect_patterns
from .portfolio import (
    get_current_prices,
    get_holdings_grouped,
    get_plan_status,
    record_trade,
)
from .schemas import (
    AlertRuleCreate,
    AlertRuleUpdate,
    DCARequest,
    DCAResponse,
    HealthResponse,
    ScoreHistoryPoint,
    WatchlistResponse,
)
from .telegram_bot import TelegramConfig, send_message
from .ws_hub import ws_endpoint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gold", tags=["GoldDesk"])

# ── Antigravity sub-router ────────────────────────────────────────
try:
    from .antigravity.api import router as antigravity_router

    router.include_router(antigravity_router)
except Exception as _e:
    import logging as _lg

    _lg.getLogger(__name__).warning("Antigravity router not loaded: %s", _e)


# ── 1. Live Snapshot ──────────────────────────────────────────────


@router.get("/snapshot", response_model=None, summary="Live gold market snapshot")
async def get_snapshot(session: AsyncSession = Depends(get_db_session)) -> dict:
    """snapshot کامل با score و self-check."""
    try:
        snap = await snapshot_service.build_snapshot(session)
        return {"success": True, "data": snap.model_dump(mode="json")}
    except Exception as exc:
        logger.exception("snapshot failed")
        return {"success": False, "data": None, "error": {"message": str(exc)}}


# ── 2. Score فقط ────────────────────────────────────────────────


@router.get("/score", summary="Current decision score only")
async def get_score(session: AsyncSession = Depends(get_db_session)) -> dict:
    try:
        snap = await snapshot_service.build_snapshot(session)
        return {"success": True, "data": snap.score.model_dump(mode="json")}
    except Exception as exc:
        logger.exception("score failed")
        return {"success": False, "error": {"message": str(exc)}}


# ── 3. History ────────────────────────────────────────────────────


@router.get("/history/score", summary="Score history (time-series)")
async def get_score_history(
    days: int = Query(7, ge=1, le=90),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(GoldScoreHistoryModel)
        .where(GoldScoreHistoryModel.score_at >= cutoff)
        .order_by(GoldScoreHistoryModel.score_at)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    items = [
        ScoreHistoryPoint(
            score_at=r.score_at,
            total=int(r.total_score),
            decision=r.decision,
            hard_stop_active=r.hard_stop_active,
        ).model_dump(mode="json")
        for r in rows
    ]
    return {"success": True, "data": {"items": items, "total": len(items)}}


@router.get("/history/snapshot", summary="Snapshot history for one symbol")
async def get_snapshot_history(
    symbol: str = Query("IR_COIN_EMAMI"),
    days: int = Query(7, ge=1, le=90),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(GoldSnapshotModel)
        .where(GoldSnapshotModel.symbol == symbol, GoldSnapshotModel.snapshot_at >= cutoff)
        .order_by(GoldSnapshotModel.snapshot_at)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    items = [
        {
            "snapshot_at": r.snapshot_at.isoformat() if r.snapshot_at else None,
            "market_price": r.market_price,
            "fair_value": r.fair_value,
            "bubble_pct": r.bubble_pct,
        }
        for r in rows
    ]
    return {"success": True, "data": {"items": items, "total": len(items)}}


# ── 4. DCA Plan ──────────────────────────────────────────────────


@router.post("/dca/plan", response_model=DCAResponse, summary="Calculate DCA plan")
async def post_dca_plan(req: DCARequest) -> DCAResponse:
    plan = dca_planner.plan_dca(
        total_capital_irt=req.total_capital_irt,
        risk_profile=req.risk_profile,
        current_score=req.current_score,
        preferred_vehicle=req.preferred_vehicle,
    )
    return DCAResponse(
        total_capital_irt=plan.total_capital_irt,
        ladder=[
            {
                "tranche": t.tranche,
                "pct": t.pct,
                "amount_irt": t.amount_irt,
                "trigger": t.trigger,
                "vehicle": t.vehicle,
                "estimated_fee_irt": t.estimated_fee_irt,
            }
            for t in plan.ladder
        ],
        recommended_vehicle=plan.recommended_vehicle,
        total_fee_irt=plan.total_fee_irt,
        net_investable_irt=plan.net_investable_irt,
        stop_loss_pct=plan.stop_loss_pct,
        take_profit_pct=plan.take_profit_pct,
    )


# ── 5. Alerts CRUD ──────────────────────────────────────────────


@router.get("/alerts/rules", summary="List alert rules")
async def list_alert_rules(session: AsyncSession = Depends(get_db_session)) -> dict:
    stmt = select(AlertRuleModel).order_by(AlertRuleModel.id)
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "success": True,
        "data": [
            {
                "id": r.id,
                "name": r.name,
                "rule_type": r.rule_type,
                "symbol": r.symbol,
                "threshold": r.threshold,
                "channel": r.channel,
                "telegram_chat_id": r.telegram_chat_id,
                "enabled": r.enabled,
                "cooldown_minutes": r.cooldown_minutes,
                "last_fired_at": r.last_fired_at.isoformat() if r.last_fired_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.post("/alerts/rules", summary="Create alert rule")
async def create_alert_rule(rule: AlertRuleCreate, session: AsyncSession = Depends(get_db_session)) -> dict:
    new_rule = AlertRuleModel(**rule.model_dump())
    session.add(new_rule)
    await session.commit()
    await session.refresh(new_rule)
    return {"success": True, "data": {"id": new_rule.id}}


@router.put("/alerts/rules/{rule_id}", summary="Update alert rule")
async def update_alert_rule(
    rule_id: int,
    update: AlertRuleUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rule = (await session.execute(select(AlertRuleModel).where(AlertRuleModel.id == rule_id))).scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="rule not found")
    for k, v in update.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    await session.commit()
    return {"success": True}


@router.delete("/alerts/rules/{rule_id}", summary="Delete alert rule")
async def delete_alert_rule(rule_id: int, session: AsyncSession = Depends(get_db_session)) -> dict:
    rule = (await session.execute(select(AlertRuleModel).where(AlertRuleModel.id == rule_id))).scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="rule not found")
    await session.delete(rule)
    await session.commit()
    return {"success": True}


@router.get("/alerts/events", summary="List alert events")
async def list_alert_events(
    days: int = Query(7, ge=1, le=90),
    unread_only: bool = Query(False),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days)
    stmt = select(AlertEventModel).where(AlertEventModel.sent_at >= cutoff)
    if unread_only:
        stmt = stmt.where(AlertEventModel.read_at.is_(None))
    stmt = stmt.order_by(desc(AlertEventModel.sent_at)).limit(200)
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "success": True,
        "data": [
            {
                "id": r.id,
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "symbol": r.symbol,
                "trigger_value": r.trigger_value,
                "threshold": r.threshold,
                "message": r.message,
                "channel": r.channel,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                "read_at": r.read_at.isoformat() if r.read_at else None,
            }
            for r in rows
        ],
    }


@router.post("/alerts/{event_id}/ack", summary="Mark alert as read")
async def ack_alert(event_id: int, session: AsyncSession = Depends(get_db_session)) -> dict:
    ev = (await session.execute(select(AlertEventModel).where(AlertEventModel.id == event_id))).scalars().first()
    if not ev:
        raise HTTPException(status_code=404, detail="event not found")
    ev.read_at = datetime.utcnow()
    await session.commit()
    return {"success": True}


@router.post("/alerts/seed", summary="Seed default alert rules (idempotent)")
async def post_seed_rules(session: AsyncSession = Depends(get_db_session)) -> dict:
    n = await seed_default_rules(session)
    return {"success": True, "data": {"inserted": n}}


# ── 6. Watchlist (Redis) ──────────────────────────────────────────


@router.get("/watchlist", response_model=WatchlistResponse, summary="Get watchlist")
async def get_watchlist() -> WatchlistResponse:
    from core.cache import get_cache

    from .constants import REDIS_KEY_WATCHLIST

    cache = get_cache()
    raw = await cache.get(REDIS_KEY_WATCHLIST)
    if raw:
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            return WatchlistResponse(
                symbols=data.get("symbols", []),
                updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            )
        except Exception:
            pass
    return WatchlistResponse(symbols=[], updated_at=None)


@router.put("/watchlist", response_model=WatchlistResponse, summary="Replace watchlist")
async def put_watchlist(payload: WatchlistResponse) -> WatchlistResponse:
    from core.cache import get_cache

    from .constants import REDIS_KEY_WATCHLIST

    cache = get_cache()
    now = datetime.utcnow()
    payload.updated_at = now
    await cache.set_persistent(
        REDIS_KEY_WATCHLIST,
        json.dumps({"symbols": payload.symbols, "updated_at": now.isoformat()}),
    )
    return payload


# ── 7. Telegram ──────────────────────────────────────────────────


@router.post("/telegram/test", summary="Send test Telegram message")
async def test_telegram(chat_id: str | None = None) -> dict:
    cfg = TelegramConfig.from_env()
    if not cfg.is_configured():
        return {"success": False, "error": {"message": "Telegram not configured"}}
    ok = await send_message(
        "✅ Temce GoldDesk test message",
        chat_id=chat_id,
        config=cfg,
    )
    return {"success": ok}


@router.get("/telegram/status", summary="Telegram configuration status")
async def telegram_status() -> dict:
    cfg = TelegramConfig.from_env()
    return {
        "success": True,
        "data": {
            "bot_configured": bool(cfg.bot_token),
            "default_chat_id_set": bool(cfg.default_chat_id),
            "enabled": cfg.enabled,
            "is_operational": cfg.is_configured(),
        },
    }


# ── 8. Health + Backtest ──────────────────────────────────────────


@router.get("/health", response_model=HealthResponse, summary="GoldDesk health")
async def health(session: AsyncSession = Depends(get_db_session)):
    """
    Health check برای Docker/K8s.
    - 200 OK: سرویس سالم
    - 503: مشکل (DB یا Redis)
    """
    from fastapi import Response

    from core.cache import get_cache

    redis_ok = False
    with contextlib.suppress(Exception):
        redis_ok = await get_cache().ping()

    db_ok = True
    try:
        await session.execute(select(func.count(AlertRuleModel.id)))
    except Exception:
        db_ok = False

    last_snap = (
        await session.execute(
            select(GoldSnapshotModel.snapshot_at).order_by(desc(GoldSnapshotModel.snapshot_at)).limit(1)
        )
    ).scalar()

    (
        await session.execute(
            select(GoldScoreHistoryModel.score_at).order_by(desc(GoldScoreHistoryModel.score_at)).limit(1)
        )
    ).scalar()

    active_rules = (
        await session.execute(
            select(func.count(AlertRuleModel.id)).where(AlertRuleModel.enabled == True)  # noqa: E712
        )
    ).scalar() or 0

    unread = (
        await session.execute(select(func.count(AlertEventModel.id)).where(AlertEventModel.read_at.is_(None)))
    ).scalar() or 0

    if not db_ok:
        return Response(
            status_code=503,
            content='{"status":"unhealthy","reason":"db"}',
            media_type="application/json",
        )

    return HealthResponse(
        brsapi_ok=db_ok,
        redis_ok=redis_ok,
        db_ok=db_ok,
        last_snapshot_at=last_snap,
        scheduler_jobs=4,
        telegram_configured=TelegramConfig.from_env().is_configured(),
        active_alert_rules=int(active_rules),
        unread_alerts=int(unread),
    )


@router.get("/backtest", summary="Run backtest on coin_emami")
async def backtest(
    days: int = Query(90, ge=30, le=365),
    bubble_threshold: float = Query(8.0, ge=0),
    symbol: str = Query("IR_COIN_EMAMI"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    r = await run_backtest(session, symbol=symbol, days=days, bubble_threshold=bubble_threshold)
    return {
        "success": True,
        "data": {
            "total_days": r.total_days,
            "signal_days": r.score_above_threshold_days,
            "forward_30d_avg_pct": round(r.forward_return_30d_avg, 2),
            "positive_count": r.forward_return_30d_positive,
            "negative_count": r.forward_return_30d_negative,
            "hit_rate_pct": round(r.hit_rate, 1),
            "warning": r.sample_warning,
        },
    }


# ── 9. Strategy Backtest (DCA simulation) ──────────────────────


@router.get("/backtest/strategy", summary="Run DCA strategy backtest")
async def strategy_backtest(
    days: int = Query(90, ge=30, le=365),
    symbol: str = Query("IR_COIN_EMAMI"),
    bubble_trigger: float = Query(5.0, ge=0),
    initial_capital: float = Query(100_000_000, ge=1_000_000),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """اجرای backtest استراتژی DCA روی داده‌های تاریخی.

    مقایسه با buy-and-hold، محاسبه alpha، max drawdown، Sharpe.
    """
    m = await run_strategy_backtest(
        session,
        symbol=symbol,
        days=days,
        bubble_trigger=bubble_trigger,
        initial_capital=initial_capital,
    )
    return {
        "success": True,
        "data": {
            "period": {
                "start": m.period_start.isoformat(),
                "end": m.period_end.isoformat(),
            },
            "initial_capital": m.initial_capital,
            "final_value": round(m.final_value, 0),
            "total_return_pct": m.total_return_pct,
            "buy_hold_return_pct": m.buy_hold_return_pct,
            "alpha_pct": m.alpha_pct,
            "hit_rate_pct": m.hit_rate_pct,
            "n_trades": m.n_trades,
            "n_successful": m.n_successful,
            "max_drawdown_pct": m.max_drawdown_pct,
            "sharpe_ratio": m.sharpe_ratio,
            "trades": [
                {
                    "date": t.date.isoformat(),
                    "tranche": t.tranche,
                    "price": t.price,
                    "amount_irt": t.amount_irt,
                    "units": t.units,
                }
                for t in m.trades
            ],
            "warning": m.warning,
        },
    }


# ── 9b. Real Historical Backtest (multiple strategies) ─────


@router.get("/backtest/real", summary="Run multi-strategy backtest on real BrsApi data")
async def real_backtest(
    days: int = Query(180, ge=60, le=730),
    symbol: str = Query("IR_COIN_EMAMI"),
    initial_capital: float = Query(100_000_000, ge=1_000_000),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """اجرای ۳ استراتژی روی داده‌های واقعی BrsApi: RSI, MA, Bubble."""
    run = await run_real_backtest(session, symbol=symbol, days=days, initial_capital=initial_capital)
    return {
        "success": True,
        "data": {
            "symbol": run.symbol,
            "period": {"start": run.period_start, "end": run.period_end},
            "initial_capital": run.initial_capital,
            "best_strategy": run.best_strategy,
            "strategies": [
                {
                    "name": s.name,
                    "total_return_pct": s.total_return_pct,
                    "buy_hold_return_pct": s.buy_hold_return_pct,
                    "alpha_pct": s.alpha_pct,
                    "n_trades": s.n_trades,
                    "n_wins": s.n_wins,
                    "hit_rate_pct": s.hit_rate_pct,
                    "max_drawdown_pct": s.max_drawdown_pct,
                    "sharpe_ratio": s.sharpe_ratio,
                    "avg_hold_days": s.avg_hold_days,
                }
                for s in run.strategies
            ],
        },
    }


# ── 10. Black-76 Options Pricing ──────────────────────────────


@router.post("/options/price", summary="Price gold option (Black-76)")
async def price_gold_option(
    forward: float,
    strike: float,
    expiry: str,  # YYYY-MM-DD
    iv: float = Query(0.25, ge=0.01, le=2.0),
    rate: float = Query(0.30, ge=0, le=1.0),
) -> dict:
    """قیمت‌گذاری Call و Put با Black-76.

    forward: قیمت آتی صندوق (NAV یا spot)
    strike: قیمت اعمال
    expiry: تاریخ سررسید
    iv: نوسان ضمنی (سالانه، پیش‌فرض ۲۵٪)
    rate: نرخ بهره بدون ریسک (پیش‌فرض ۳۰٪)
    """
    from datetime import date as _date

    try:
        exp = _date.fromisoformat(expiry)
    except ValueError:
        raise HTTPException(400, f"invalid date format: {expiry}")
    r = price_option(forward=forward, strike=strike, expiry=exp, iv=iv, rate=rate)
    return {
        "success": True,
        "data": {
            "call": round(r.call, 2),
            "put": round(r.put, 2),
            "forward": r.forward,
            "strike": r.strike,
            "time_years": round(r.time_to_expiry_years, 4),
            "iv": r.iv,
            "rate": r.rate,
            "d1": round(r.d1, 4),
            "d2": round(r.d2, 4),
            "greeks": {
                "delta": round(r.greeks.delta, 4),
                "gamma": round(r.greeks.gamma, 6),
                "vega": round(r.greeks.vega, 4),
                "theta": round(r.greeks.theta, 4),
                "rho": round(r.greeks.rho, 4),
            },
        },
    }


@router.post("/options/collar", summary="Protective Collar strategy")
async def protective_collar_endpoint(
    spot: float,
    put_strike: float,
    call_strike: float,
    expiry: str,
    iv: float = Query(0.25, ge=0.01, le=2.0),
    rate: float = Query(0.30, ge=0, le=1.0),
) -> dict:
    """استراتژی Protective Collar.

    نگهداری spot + خرید put در K1 + فروش call در K2.
    """
    from datetime import date as _date

    try:
        exp = _date.fromisoformat(expiry)
    except ValueError:
        raise HTTPException(400, f"invalid date format: {expiry}")
    if call_strike <= put_strike:
        raise HTTPException(400, "call_strike must be > put_strike")
    r = protective_collar(spot, put_strike, call_strike, exp, iv, rate)
    return {
        "success": True,
        "data": {
            "cost": round(r.cost, 2),
            "floor": r.floor,
            "cap": r.cap,
            "put_premium": round(r.put_premium, 2),
            "call_premium": round(r.call_premium, 2),
            "spot": r.spot,
            "time_years": round(r.time_years, 4),
        },
    }


# ── 11. WebSocket Live Stream ─────────────────────────────────


@router.websocket("/ws")
async def gold_websocket(websocket: WebSocket) -> None:
    """WebSocket — پخش زنده snapshot هر ۵ ثانیه."""
    await ws_endpoint(websocket)


# ── 12. API Tokens (برای استفاده خارجی) ────────────────────


@router.post("/tokens", summary="Generate a new API token")
async def create_token(
    name: str = Query(..., min_length=1, max_length=64),
    scopes: str = Query("read", description="Comma-separated: read,write,admin"),
) -> dict:
    """ساخت token جدید. plain token فقط یک‌بار نمایش داده می‌شود.

    scopes: read (GET) | write (POST/PUT/DELETE) | admin (همه)
    """
    from .api_token import generate_token, save_token

    scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
    valid = {"read", "write", "admin"}
    invalid = [s for s in scope_list if s not in valid]
    if invalid:
        raise HTTPException(400, f"invalid scopes: {invalid}")
    if not scope_list:
        scope_list = ["read"]

    plain, info = generate_token(name, scope_list)
    await save_token(plain, info)
    return {
        "success": True,
        "data": {
            "token": plain,  # فقط یک‌بار نمایش داده می‌شود
            "token_id": info.token_id,
            "name": info.name,
            "scopes": info.scopes,
            "warning": "این token را ذخیره کنید. دوباره نمایش داده نمی‌شود.",
        },
    }


@router.get("/tokens", summary="List API tokens")
async def list_api_tokens() -> dict:
    """لیست tokenهای فعال (بدون plain token)."""
    from .api_token import list_tokens

    tokens = await list_tokens()
    return {
        "success": True,
        "data": [
            {
                "token_id": t.token_id,
                "name": t.name,
                "scopes": t.scopes,
                "enabled": t.enabled,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
            }
            for t in tokens
        ],
    }


@router.delete("/tokens/{token_id}", summary="Revoke a token")
async def delete_token(token_id: str) -> dict:
    from .api_token import revoke_token

    ok = await revoke_token(token_id)
    return {"success": ok}


# ── 13. OpenAPI Docs (مسیر اضافی) ────────────────────────────


# ── 16. Portfolio (P&L + DCA tracker) ─────────────────────────


class HoldingCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    display_name: str = Field(..., min_length=1, max_length=64)
    vehicle: str = Field("etf", max_length=16)
    quantity: float = Field(..., gt=0)
    buy_price: float = Field(..., gt=0)
    buy_amount_irt: float = Field(..., gt=0)
    buy_fee_pct: float = Field(0.0, ge=0)
    note: str | None = None


class DCAPlanCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    total_capital_irt: float = Field(..., gt=0)
    risk_profile: Literal["conservative", "balanced", "aggressive"] = "balanced"
    vehicle: Literal["etf", "cert", "melted", "coin"] = "etf"
    current_score: int = Field(60, ge=0, le=100)
    stop_loss_pct: float = Field(8.0, ge=0)
    take_profit_pct: float = Field(25.0, ge=0)


class TradeCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    action: Literal["buy", "sell"]
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    amount_irt: float = Field(..., gt=0)
    fee_pct: float = Field(0.0, ge=0)
    holding_id: int | None = None
    plan_id: int | None = None
    note: str | None = None


@router.get("/portfolio", summary="Get portfolio summary with P&L")
async def get_portfolio(session: AsyncSession = Depends(get_db_session)) -> dict:
    """خلاصه portfolio با P&L بر اساس قیمت‌های فعلی از snapshot."""
    snap = await get_hot_snapshot()
    prices = get_current_prices(snap)
    summary = await get_holdings_grouped(session, prices)
    return {
        "success": True,
        "data": {
            "total_cost": summary.total_cost,
            "total_value": summary.total_value,
            "total_pnl": summary.total_pnl,
            "total_pnl_pct": summary.total_pnl_pct,
            "holdings": [
                {
                    "symbol": h.symbol,
                    "display_name": h.display_name,
                    "quantity": h.quantity,
                    "avg_buy_price": h.avg_buy_price,
                    "current_price": h.current_price,
                    "cost_basis": h.cost_basis,
                    "current_value": h.current_value,
                    "pnl_irt": h.pnl_irt,
                    "pnl_pct": h.pnl_pct,
                    "n_purchases": h.n_purchases,
                }
                for h in summary.holdings
            ],
            "snapshot_at": snap.get("snapshot_at") if snap else None,
        },
    }


@router.post("/portfolio/holdings", summary="Add a new holding (purchase)")
async def add_holding(
    h: HoldingCreate,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    from .models import GoldHoldingModel

    new_h = GoldHoldingModel(**h.model_dump())
    session.add(new_h)
    await session.commit()
    await session.refresh(new_h)
    return {"success": True, "data": {"id": new_h.id}}


@router.delete("/portfolio/holdings/{holding_id}", summary="Remove a holding")
async def delete_holding(
    holding_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    from .models import GoldHoldingModel

    h = await session.get(GoldHoldingModel, holding_id)
    if not h:
        raise HTTPException(404, "holding not found")
    await session.delete(h)
    await session.commit()
    return {"success": True}


@router.post("/portfolio/dca", summary="Create a DCA plan")
async def create_dca_plan(
    p: DCAPlanCreate,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """ساخت پلن DCA با محاسبه ladder از dca_planner."""
    from .dca_planner import plan_dca
    from .models import GoldDCAPlanModel

    plan = plan_dca(
        total_capital_irt=p.total_capital_irt,
        risk_profile=p.risk_profile,
        current_score=p.current_score,
        preferred_vehicle=p.vehicle,
    )
    ladder_json = json.dumps(
        [
            {
                "tranche": t.tranche,
                "pct": t.pct,
                "amount_irt": t.amount_irt,
                "trigger": t.trigger,
                "vehicle": t.vehicle,
                "estimated_fee_irt": t.estimated_fee_irt,
            }
            for t in plan.ladder
        ]
    )
    new_plan = GoldDCAPlanModel(
        name=p.name,
        total_capital_irt=p.total_capital_irt,
        risk_profile=p.risk_profile,
        vehicle=p.vehicle,
        ladder_json=ladder_json,
        current_score=p.current_score,
        stop_loss_pct=p.stop_loss_pct,
        take_profit_pct=p.take_profit_pct,
    )
    session.add(new_plan)
    await session.commit()
    await session.refresh(new_plan)
    return {
        "success": True,
        "data": {
            "id": new_plan.id,
            "name": new_plan.name,
            "total_capital": new_plan.total_capital_irt,
            "ladder": json.loads(new_plan.ladder_json),
            "stop_loss_pct": new_plan.stop_loss_pct,
            "take_profit_pct": new_plan.take_profit_pct,
        },
    }


@router.get("/portfolio/dca", summary="List DCA plans with status")
async def list_dca_plans(
    current_score: int = Query(60, ge=0, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    from .models import GoldDCAPlanModel

    rows = (await session.execute(select(GoldDCAPlanModel).order_by(GoldDCAPlanModel.id))).scalars().all()
    return {
        "success": True,
        "data": [
            {
                "plan_id": p.id,
                "name": p.name,
                "status": _plan_status_dict(get_plan_status(p, current_score)),
            }
            for p in rows
        ],
    }


def _plan_status_dict(s) -> dict:
    return {
        "total_capital": s.total_capital,
        "executed": s.executed,
        "remaining": s.remaining,
        "next_tranche_pct": s.next_tranche_pct,
        "next_tranche_amount": s.next_tranche_amount,
        "next_trigger": s.next_trigger,
        "current_score": s.current_score,
        "stop_loss_pct": s.stop_loss_pct,
        "take_profit_pct": s.take_profit_pct,
    }


@router.post("/portfolio/dca/{plan_id}/execute", summary="Mark a DCA tranche as executed")
async def execute_dca_tranche(
    plan_id: int,
    tranche: int = Query(..., ge=1, le=10),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """افزایش executed_tranches (manual confirmation)."""
    from .models import GoldDCAPlanModel

    plan = await session.get(GoldDCAPlanModel, plan_id)
    if not plan:
        raise HTTPException(404, "plan not found")
    if tranche > plan.executed_tranches + 1:
        raise HTTPException(400, "must execute in order")
    plan.executed_tranches = tranche
    plan.updated_at = datetime.utcnow()
    await session.commit()
    return {"success": True, "data": {"executed_tranches": plan.executed_tranches}}


@router.delete("/portfolio/dca/{plan_id}", summary="Delete a DCA plan")
async def delete_dca_plan(
    plan_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    from .models import GoldDCAPlanModel

    plan = await session.get(GoldDCAPlanModel, plan_id)
    if not plan:
        raise HTTPException(404, "plan not found")
    await session.delete(plan)
    await session.commit()
    return {"success": True}


@router.post("/portfolio/trades", summary="Record a buy/sell trade")
async def post_trade(
    t: TradeCreate,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    trade = await record_trade(
        session,
        symbol=t.symbol,
        action=t.action,
        quantity=t.quantity,
        price=t.price,
        amount_irt=t.amount_irt,
        fee_pct=t.fee_pct,
        holding_id=t.holding_id,
        plan_id=t.plan_id,
        note=t.note,
    )
    return {
        "success": True,
        "data": {
            "id": trade.id,
            "fee_irt": trade.fee_irt,
            "pnl_irt": trade.pnl_irt,
        },
    }


@router.get("/portfolio/trades", summary="List recent trades")
async def list_trades(
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    from .models import GoldTradeModel

    rows = (
        (await session.execute(select(GoldTradeModel).order_by(desc(GoldTradeModel.traded_at)).limit(limit)))
        .scalars()
        .all()
    )
    return {
        "success": True,
        "data": [
            {
                "id": r.id,
                "symbol": r.symbol,
                "action": r.action,
                "quantity": r.quantity,
                "price": r.price,
                "amount_irt": r.amount_irt,
                "fee_irt": r.fee_irt,
                "pnl_irt": r.pnl_irt,
                "note": r.note,
                "traded_at": r.traded_at.isoformat() if r.traded_at else None,
            }
            for r in rows
        ],
    }


# ── 17. AI Chat Assistant ────────────────────────────────────


# ── 18. Live Signals (real-time) ──────────────────────────────


@router.get("/signals/recent", summary="Recent live signals")
async def get_recent_signals(limit: int = Query(20, ge=1, le=100)) -> dict:
    """signalهای اخیر (cooldown: 10 دقیقه)."""
    try:
        from core.cache import get_cache

        from .live_signals import REDIS_KEY_RECENT_SIGNALS

        cache = get_cache()
        raw = await cache.get(REDIS_KEY_RECENT_SIGNALS) or []
        items: list[dict] = json.loads(raw) if isinstance(raw, str) else raw
        items.sort(key=lambda x: x.get("ts", 0), reverse=True)
        return {
            "success": True,
            "data": {
                "count": len(items[:limit]),
                "signals": [it.get("signal", it) for it in items[:limit]],
            },
        }
    except Exception as exc:
        return {"success": True, "data": {"count": 0, "signals": [], "error": str(exc)}}


@router.post("/signals/detect", summary="Manually trigger signal detection")
async def post_detect_signals() -> dict:
    """تشخیص دستی سیگنال از snapshot فعلی (برای تست)."""
    snap = await get_hot_snapshot()
    if not snap:
        return {"success": False, "error": {"message": "no snapshot available"}}
    signals = await detect_and_broadcast(snap)
    return {
        "success": True,
        "data": {"count": len(signals), "signals": [s.to_dict() for s in signals]},
    }


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


@router.post("/chat", summary="Ask GoldDesk AI assistant")
async def post_chat(
    req: ChatRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """پرسش از دستیار هوشمند. snapshot + portfolio + patterns به context اضافه می‌شود."""
    snap = await get_hot_snapshot()
    portfolio_data = None
    try:
        prices = get_current_prices(snap)
        portfolio = await get_holdings_grouped(session, prices)
        portfolio_data = {
            "total_value": portfolio.total_value,
            "total_cost": portfolio.total_cost,
            "total_pnl": portfolio.total_pnl,
            "total_pnl_pct": portfolio.total_pnl_pct,
        }
    except Exception:
        pass

    patterns_data = None
    try:
        report = await detect_patterns(session)
        patterns_data = {
            "patterns": [
                {
                    "type": p.pattern_type,
                    "confidence": p.confidence,
                    "description": p.description,
                    "expected_direction": p.expected_direction,
                }
                for p in report.patterns
            ],
            "recommendation": report.recommendation,
            "summary": report.summary,
        }
    except Exception:
        pass

    answer = await ask_gold_assistant(req.message, snap, portfolio_data, patterns_data)
    return {"success": True, "data": {"answer": answer}}


# ── 14. Hot Path (polling سریع) ──────────────────────────────


@router.get("/hot", summary="Lightweight hot path for fast polling")
async def get_hot() -> dict:
    """snapshot کم‌حجم برای polling هر ۱۰ ثانیه.

    شامل: refs + score + signal + coin_emami + ۳ صندوق برتر.
    latency < 50ms.
    """
    snap = await get_hot_snapshot()
    return build_hotpath_response(snap)


# ── 15. AI Pattern Detection ─────────────────────────────────


@router.get("/patterns", summary="Detect patterns in historical data")
async def get_patterns(
    days: int = Query(90, ge=30, le=365),
    symbol: str = Query("IR_COIN_EMAMI"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """تشخیص خودکار الگوهای bubble در داده‌های تاریخی.

    الگوهای قابل‌تشخیص: mean_reversion, trend_continuation,
    spike_crash, vol_regime.
    """
    report = await detect_patterns(session, symbol=symbol, days=days)
    return {
        "success": True,
        "data": {
            "symbol": report.symbol,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "summary": report.summary,
            "recommendation": report.recommendation,
            "patterns": [
                {
                    "type": p.pattern_type,
                    "confidence": round(p.confidence, 2),
                    "description": p.description,
                    "expected_direction": p.expected_direction,
                    "expected_magnitude_pct": p.expected_magnitude_pct,
                    "historical_hit_rate": round(p.historical_hit_rate, 1),
                    "sample_size": p.sample_size,
                }
                for p in report.patterns
            ],
        },
    }


@router.get("/docs/endpoints", summary="List all GoldDesk endpoints")
async def list_endpoints() -> dict:
    """لیست همه endpointهای GoldDesk با نوع و توضیح — برای ابزارهای خارجی."""
    return {
        "success": True,
        "data": {
            "base_url": "/api/gold",
            "auth": "Bearer token in Authorization header (for write endpoints)",
            "endpoints": [
                {"method": "GET", "path": "/snapshot", "scope": "read", "desc": "Live snapshot"},
                {"method": "GET", "path": "/score", "scope": "read", "desc": "Just score"},
                {"method": "GET", "path": "/history/score?days=7", "scope": "read", "desc": "Score time-series"},
                {
                    "method": "GET",
                    "path": "/history/snapshot?symbol=&days=",
                    "scope": "read",
                    "desc": "Asset time-series",
                },
                {"method": "POST", "path": "/dca/plan", "scope": "read", "desc": "DCA calculation"},
                {"method": "GET", "path": "/alerts/rules", "scope": "read", "desc": "List alert rules"},
                {"method": "POST", "path": "/alerts/rules", "scope": "write", "desc": "Create alert rule"},
                {"method": "GET", "path": "/alerts/events?days=7", "scope": "read", "desc": "Alert events history"},
                {"method": "POST", "path": "/alerts/{id}/ack", "scope": "write", "desc": "Mark alert read"},
                {"method": "POST", "path": "/options/price", "scope": "read", "desc": "Black-76 option price"},
                {"method": "POST", "path": "/options/collar", "scope": "read", "desc": "Protective Collar"},
                {"method": "GET", "path": "/backtest?days=90", "scope": "read", "desc": "Signal backtest"},
                {
                    "method": "GET",
                    "path": "/backtest/strategy?days=90",
                    "scope": "read",
                    "desc": "DCA strategy backtest",
                },
                {"method": "POST", "path": "/telegram/test", "scope": "write", "desc": "Test Telegram"},
                {"method": "GET", "path": "/health", "scope": "read", "desc": "Health status"},
                {"method": "POST", "path": "/tokens", "scope": "admin", "desc": "Create API token"},
                {"method": "GET", "path": "/tokens", "scope": "admin", "desc": "List tokens"},
                {"method": "WS", "path": "/ws", "scope": "read", "desc": "Live WebSocket"},
            ],
        },
    }


# ── 19. Prometheus Metrics ───────────────────────────────────


@router.get("/metrics", summary="Prometheus metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus text format برای scrape."""
    return Response(
        content=render_prometheus(),
        media_type="text/plain; version=0.0.4",
    )


# ── 20. Macro & News ───────────────────────────────────────


@router.get("/macro", summary="Macro events affecting gold market")
async def get_macro_events(limit: int = Query(20, ge=1, le=100)) -> dict:
    """رویدادهای کلان اقتصادی (CPI، نرخ بهره، M2، تقاضا) + تأثیر بر طلا."""
    events = await fetch_macro_events()
    multiplier = compute_macro_multiplier(events)
    items = sorted(events, key=lambda e: e.published_at, reverse=True)[:limit]
    return {
        "success": True,
        "data": {
            "count": len(items),
            "macro_multiplier": round(multiplier, 3),
            "interpretation": (
                "بسیار مثبت (خرید قوی)"
                if multiplier > 0.5
                else "مثبت"
                if multiplier > 0.1
                else "خنثی"
                if abs(multiplier) <= 0.1
                else "منفی"
                if multiplier > -0.5
                else "بسیار منفی (فروش)"
            ),
            "events": [
                {
                    "title": e.title,
                    "source": e.source,
                    "category": e.category,
                    "impact_score": e.impact_score,
                    "confidence": e.confidence,
                    "explanation": e.explanation,
                    "published_at": e.published_at.isoformat(),
                }
                for e in items
            ],
        },
    }


@router.post("/macro/scrape", summary="Scrape CBI for news")
async def post_scrape_cbi() -> dict:
    """scrape دستی CBI (برای تست یا refresh فوری)."""
    events = await scrape_cbi_news()
    return {"success": True, "data": {"count": len(events), "events": [e.to_dict() for e in events]}}


# ── 21. Crypto + Multi-Currency ────────────────────────────


@router.get("/crypto", summary="Cryptocurrency prices")
async def get_crypto(force_refresh: bool = Query(False)) -> dict:
    """قیمت ارزهای دیجیتال از CoinGecko + نرخ تبدیل USD/IRT."""
    try:
        from core.cache import get_cache

        from .crypto import REDIS_KEY_CRYPTO

        cache = get_cache()
        if not force_refresh:
            raw = await cache.get(REDIS_KEY_CRYPTO)
            if raw:
                import json

                data = json.loads(raw) if isinstance(raw, str) else raw
                return {"success": True, "data": data}
    except Exception:
        pass

    # نیاز به USD/IRT rate از snapshot
    snap = await get_hot_snapshot()
    usd_irt = (snap.get("references", {}) or {}).get("usd_irt", 70000) if snap else 70000

    prices = await fetch_crypto_prices(usd_irt)
    items = [
        {
            "symbol": p.symbol,
            "name_fa": p.name_fa,
            "price_usd": p.price_usd,
            "price_irt": p.price_irt,
            "change_24h_pct": p.change_24h_pct,
            "source": p.source,
        }
        for p in prices
    ]
    result = {"count": len(items), "usd_irt_rate": usd_irt, "assets": items}

    try:
        import json

        from core.cache import get_cache

        from .crypto import REDIS_KEY_CRYPTO

        cache = get_cache()
        await cache.set(REDIS_KEY_CRYPTO, json.dumps(result, default=str), ttl=300)
    except Exception:
        pass

    return {"success": True, "data": result}


@router.get("/fx", summary="Multi-currency FX rates (USD base)")
async def get_fx() -> dict:
    """نرخ FX از open.er-api.com (EUR, GBP, JPY, ...)."""
    rates = await fetch_fx_rates("USD")
    return {"success": True, "data": {"base": "USD", "rates": rates, "count": len(rates)}}


# ── 22. Forecast (پیش‌بینی قیمت) ───────────────────────────────

from .forecaster import forecast_all, forecast_symbol


@router.get("/forecast", summary="Forecast gold/coin prices (7d & 30d)")
async def get_forecast(
    symbol: str = Query("IR_COIN_EMAMI", description="نماد: IR_COIN_EMAMI | IR_GOLD_18K | XAUUSD | ..."),
    days: int = Query(60, ge=20, le=365, description="lookback برای آموزش مدل"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """پیش‌بینی قیمت ۷ و ۳۰ روز آینده با ۳ مدل (LR + EMA + Drift) + باند اطمینان 95%."""
    result = await forecast_symbol(session, symbol=symbol, days=days)
    return {
        "success": True,
        "data": {
            "symbol": result.symbol,
            "last_price": result.last_price,
            "last_date": result.last_date,
            "lookback_days": result.lookback_days,
            "volatility_daily_pct": result.volatility_daily_pct,
            "trend_daily_pct": result.trend_daily_pct,
            "r_squared": result.r_squared,
            "confidence": result.confidence,
            "summary": result.summary,
            "recommendation": result.recommendation,
            "model_weights": result.model_weights,
            "forecasts": [
                {
                    "horizon_days": f.horizon_days,
                    "predicted_price": f.predicted_price,
                    "lower_band": f.lower_band,
                    "upper_band": f.upper_band,
                    "expected_return_pct": f.expected_return_pct,
                    "model": f.model,
                }
                for f in result.forecasts
            ],
        },
    }


@router.get("/forecast/all", summary="Forecast multiple symbols")
async def get_forecast_all(
    days: int = Query(60, ge=20, le=365),
    symbols: str = Query("IR_COIN_EMAMI,IR_GOLD_18K,XAUUSD", description="comma separated"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    results = await forecast_all(session, symbols=syms, days=days)
    return {
        "success": True,
        "data": {
            "count": len(results),
            "items": [
                {
                    "symbol": r.symbol,
                    "last_price": r.last_price,
                    "volatility_daily_pct": r.volatility_daily_pct,
                    "trend_daily_pct": r.trend_daily_pct,
                    "r_squared": r.r_squared,
                    "confidence": r.confidence,
                    "summary": r.summary,
                    "recommendation": r.recommendation,
                    "forecasts": [
                        {
                            "horizon_days": f.horizon_days,
                            "predicted_price": f.predicted_price,
                            "expected_return_pct": f.expected_return_pct,
                        }
                        for f in r.forecasts
                    ],
                }
                for r in results
            ],
        },
    }
