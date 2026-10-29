"""FastAPI router — ۸ گروه endpoint.

prefix: /gold (بدون auth چون شخصی است)
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from core.time import utc_now_naive

from . import dca_planner, phase1, phase2, snapshot_service
from .alert_engine import seed_default_rules
from .backtest import run_backtest
from .backtest_real import run_real_backtest
from .backtest_runner import run_strategy_backtest
from .black76 import price_option, protective_collar
from .chat import ask_gold_assistant
from .constants import PORTFOLIO_PERFORMANCE_WINDOW_DAYS
from .crypto import fetch_crypto_prices, fetch_fx_rates
from .freshness import build_freshness_report
from .hotpath import build_hotpath_response, get_hot_snapshot
from .live_signals import detect_and_broadcast
from .macro_news import compute_macro_multiplier, fetch_macro_events, scrape_cbi_news
from .metrics import render_prometheus
from .models import AlertEventModel, AlertRuleModel, GoldScoreHistoryModel, GoldSnapshotModel
from .pattern_detector import detect_patterns
from .phase1_schemas import WhatIfRequest
from .portfolio import (
    HoldingDeletedError,
    HoldingNotFoundError,
    build_portfolio_returns,
    build_tax_summary,
    build_trades_csv,
    get_current_prices,
    get_holdings_grouped,
    get_plan_status,
    load_holdings_and_trades,  # noqa: F401 — برای monkeypatch در تست قرارداد API
    record_trade,
)
from .portfolio_history import (
    build_performance_report,
    capture_portfolio_value,
    load_value_history,
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


async def _require_admin_user(request: Request) -> dict:
    """Admin gate for API-token administration (audit SEC-02).

    The mount-level dependency only proves "a real user". Minting tokens that
    carry the ``admin`` scope, and listing/revoking other people's, therefore
    needs an explicit role check.
    """
    from apps.api.dependencies import get_current_user
    from core.enums.rbac import has_role

    user = await get_current_user(authorization=request.headers.get("authorization", ""))
    if not has_role(user.get("roles", []), "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions: requires admin")
    return user


router = APIRouter(prefix="/gold", tags=["GoldDesk"])

# Anonymous-by-policy routes, kept on their own router so the personal surface
# can be mounted behind a real authenticated user (see ``apps/api/router.py``).
# Three routes and why each one is exempt:
#   * ``/gold/health``          — container/K8s liveness probe; a probe holds no JWT.
#   * ``/gold/assistant-rules`` — the spec card the *pre-login* ``/markets/gold``
#                                and ``/markets/silver`` pages render.
#   * ``/gold/ws``              — a socket, so it verifies its own token inside
#                                the handler instead of via the router dependency.
# Everything else on ``router`` (portfolio, alerts, tokens, chats, trades, …) is
# personal data and must resolve an authenticated user.
anonymous_router = APIRouter(prefix="/gold", tags=["GoldDesk"])

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
    except Exception:
        logger.exception("snapshot failed")
        raise HTTPException(503, {"success": False, "error": "snapshot_unavailable"})


# ── 1b. Phase 1 Data Terminal (parity surface, preview-only) ─────


@router.get(
    "/terminal",
    response_model=None,
    summary="Phase 1 gold data terminal (ticker + physical + funds + certificates)",
)
async def get_gold_terminal(session: AsyncSession = Depends(get_db_session)) -> dict:
    """جدول‌های فاز ۱: تیکر ثابت، طلا و سکه، صندوق‌ها و گواهی سپرده.

    همهٔ مبالغ ریال هستند. مقدار ناموجود ``null`` برمی‌گردد (هرگز صفر کاذب)
    و دلیل آن در ``data_gaps`` همان ردیف می‌آید. این مسیر هیچ سفارشی ثبت
    نمی‌کند؛ ``capabilities.orders`` همیشه ``false`` است.
    """
    try:
        data = await phase1.build_terminal(session)
        return {"success": True, "data": data.model_dump(mode="json")}
    except Exception:
        logger.exception("gold terminal failed")
        raise HTTPException(503, {"success": False, "error": "terminal_unavailable"})


@router.post(
    "/what-if",
    response_model=None,
    summary="Preview intrinsic/bubble implied by manual XAU/USD and USD/IRR",
)
async def post_gold_what_if(
    body: WhatIfRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """ماشین‌حساب سناریو — فقط پیش‌نمایش.

    ورودی‌ها: XAU/USD و دلار آزاد به ریال. خروجی ارزش ذاتی، حباب و USD ضمنی
    را زیر همان دو نرخ بازمحاسبه می‌کند و با برچسب ``SAMPLE`` برمی‌گرداند.
    هیچ ردیفی نوشته یا بازنویسی نمی‌شود و دادهٔ LIVE دست‌نخورده می‌ماند.
    """
    try:
        data = await phase1.build_what_if(session, body.xau_usd, body.usd_irt_rial)
        return {"success": True, "data": data.model_dump(mode="json")}
    except Exception:
        logger.exception("gold what-if failed")
        raise HTTPException(503, {"success": False, "error": "terminal_unavailable"})


# ── 1c. Phase 2 market coverage (read-only, no trading surface) ──


@router.get(
    "/tehran-board",
    response_model=None,
    summary="Tehran shop/banking board — price, spread vs official, bubble, implied USD",
)
async def get_tehran_board(session: AsyncSession = Depends(get_db_session)) -> dict:
    """تابلو خرده‌فروشی/بنکداری تهران.

    قیمت، تغییر، ارزش ذاتی، حباب، USD ضمنی و اختلاف با قیمت رسمی جدول فاز ۱.
    منبع قیمت تهران متصل نیست؛ ردیف‌ها با ``tehran_price=null`` و
    ``quality="NO_DATA"`` برمی‌گردند و دلیل در ``data_gaps`` می‌آید — ستون‌ها
    حذف نمی‌شوند. هیچ سفارش/پرداختی در این مسیر وجود ندارد.
    """
    try:
        data = await phase2.load_tehran_board(session)
        return {"success": True, "data": data.model_dump(mode="json")}
    except Exception:
        logger.exception("gold tehran board failed")
        raise HTTPException(503, {"success": False, "error": "market_coverage_unavailable"})


@router.get(
    "/platforms",
    response_model=None,
    summary="Online gold platforms — price comparison only (no buy/payment)",
)
async def get_gold_platforms(session: AsyncSession = Depends(get_db_session)) -> dict:
    """مقایسهٔ قیمت بسترهای آنلاین طلا — فقط اطلاعات قیمت.

    بدون منبع قیمتِ مستند، ``rows`` خالی و ``source_status="not_connected"``
    است. هیچ دکمهٔ خرید، سبد، checkout یا پرداختی وجود ندارد؛
    ``capabilities`` همهٔ این قابلیت‌ها را ``false`` اعلام می‌کند.
    """
    try:
        data = await phase2.load_platforms(session)
        return {"success": True, "data": data.model_dump(mode="json")}
    except Exception:
        logger.exception("gold platforms failed")
        raise HTTPException(503, {"success": False, "error": "market_coverage_unavailable"})


@router.get(
    "/returns-matrix",
    response_model=None,
    summary="Returns matrix (1m/3m/6m/9m/1y) in Rial or USD",
)
async def get_returns_matrix(
    base_currency: Literal["IRR", "USD"] = Query("IRR"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """ماتریس بازدهی دارایی‌ها با سوییچ ریال/دلار.

    بازده سادهٔ نقطه‌به‌نقطه؛ بازه‌ای که دادهٔ کافی ندارد ``incomplete`` یا
    ``no_data`` با دلیل فارسی برچسب می‌گیرد. همبستگی فقط روی بازده‌های روز
    مشترک و بدون نگاه به آینده محاسبه می‌شود.
    """
    try:
        data = await phase2.build_returns_matrix(session, base_currency=base_currency)
        return {"success": True, "data": data.model_dump(mode="json")}
    except Exception:
        logger.exception("gold returns matrix failed")
        raise HTTPException(503, {"success": False, "error": "market_coverage_unavailable"})


@router.get(
    "/fund-map",
    response_model=None,
    summary="Gold fund market map + market-value summary",
)
async def get_fund_map(
    size_metric: Literal["trade_value", "market_value"] = Query("trade_value"),
    top_n: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """نقشهٔ بازار صندوق‌های طلا + خلاصهٔ ارزش بازار.

    اندازه با ارزش معاملات (پیش‌فرض) یا ارزش بازار؛ رنگ در فرانت‌اند از
    ``color_scale_pct`` (±۴٪) استفاده می‌کند. اندازهٔ نامعتبر/صفر حذف می‌شود و
    سهم‌ها هرگز ``Infinity``/``NaN`` نیستند. کلیک روی هر خانه به
    ``href`` یعنی ردیف همان صندوق در جدول فاز ۱ می‌رود.
    """
    try:
        data = await phase2.build_fund_map(session, size_metric=size_metric, top_n=top_n)
        return {"success": True, "data": data.model_dump(mode="json")}
    except Exception:
        logger.exception("gold fund map failed")
        raise HTTPException(503, {"success": False, "error": "market_coverage_unavailable"})


# ── 2. Score فقط ────────────────────────────────────────────────


@router.get("/score", summary="Current decision score only")
async def get_score(session: AsyncSession = Depends(get_db_session)) -> dict:
    try:
        snap = await snapshot_service.build_snapshot(session)
        return {"success": True, "data": snap.score.model_dump(mode="json")}
    except Exception:
        logger.exception("score failed")
        raise HTTPException(503, {"success": False, "error": "snapshot_unavailable"})


# ── 2b. قواعد دستیار طلا و نقره (منبع واحد: ``acceptance.yaml``) ──


@anonymous_router.get(
    "/assistant-rules",
    response_model=None,
    summary="Gold/silver assistant rules — fees, value filter, market hours",
)
async def get_gold_assistant_rules() -> dict:
    """قواعد بخش‌های ۲۰، ۲۶، ۲۷.۱ و ۲۷.۳ سند، از ``acceptance.yaml``.

    صفحه‌های طلا و نقره همین را می‌خوانند تا هیچ نرخ یا آستانه‌ای در فرانت‌اند
    هاردکد نشود و گیت سمت سرور هم همان اعداد را داشته باشد.
    """
    try:
        from core.config.acceptance_loader import get_assistant_rules

        return {"success": True, "data": get_assistant_rules()}
    except Exception:  # noqa: BLE001 — شکل پاسخ، مطابق بقیهٔ این ماژول
        logger.exception("assistant rules failed")
        raise HTTPException(503, {"success": False, "error": "snapshot_unavailable"})


# ── 3. History ────────────────────────────────────────────────────


@router.get("/history/score", summary="Score history (time-series)")
async def get_score_history(
    days: int = Query(7, ge=1, le=90),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    cutoff = utc_now_naive() - timedelta(days=days)
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
    cutoff = utc_now_naive() - timedelta(days=days)
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
    cutoff = utc_now_naive() - timedelta(days=days)
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
    ev.read_at = utc_now_naive()
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
        with contextlib.suppress(Exception):
            data = json.loads(raw) if isinstance(raw, str) else raw
            return WatchlistResponse(
                symbols=data.get("symbols", []),
                updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            )
    return WatchlistResponse(symbols=[], updated_at=None)


@router.put("/watchlist", response_model=WatchlistResponse, summary="Replace watchlist")
async def put_watchlist(payload: WatchlistResponse) -> WatchlistResponse:
    from core.cache import get_cache

    from .constants import REDIS_KEY_WATCHLIST

    cache = get_cache()
    now = utc_now_naive()
    payload.updated_at = now
    await cache.set_persistent(
        REDIS_KEY_WATCHLIST,
        json.dumps({"symbols": payload.symbols, "updated_at": now.isoformat()}),
    )
    return payload


# ── 7. Telegram ──────────────────────────────────────────────────


@router.post("/telegram/test", summary="Send test Telegram message")
async def test_telegram(request: Request, chat_id: str | None = None) -> dict:
    cfg = TelegramConfig.from_env()
    if not cfg.is_configured():
        return {"success": False, "error": {"message": "Telegram not configured"}}
    # chat_id از query می‌آید (سازگار با گذشته) وگرنه از بدنهٔ JSON خوانده می‌شود.
    # فقط خطای تجزیهٔ JSON گرفته می‌شود؛ بقیهٔ خطاها باید بالا بروند.
    import json

    if not chat_id:
        try:
            body = await request.json()
            chat_id = body.get("chat_id") if body else None
        except json.JSONDecodeError:
            chat_id = None
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


@anonymous_router.get("/health", response_model=HealthResponse, summary="GoldDesk health")
async def health(session: AsyncSession = Depends(get_db_session)):
    """
    Health check برای Docker/K8s.
    - 200 OK: سرویس سالم
    - 503: مشکل (DB یا Redis یا BRSApi)
    """
    import contextlib

    from fastapi import Response

    from core.cache import get_cache

    redis_ok = False
    with contextlib.suppress(Exception):
        redis_ok = await get_cache().ping()

    # Use freshness report to determine BRS API status
    brsapi_ok_real = False
    try:
        from .freshness import build_freshness_report
        freshness = await build_freshness_report(session)
        # BRS API is OK if overall status is ok and there are ok sources
        brsapi_ok_real = freshness["overall"] == "ok" and freshness["counts"]["ok"] > 0
    except Exception:
        logger.warning("Failed to build freshness report for health check")

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

    if not db_ok or not redis_ok:
        return Response(
            status_code=503,
            content='{"status":"unhealthy","reason":"redis_or_db"}',
            media_type="application/json",
        )

    return HealthResponse(
        brsapi_ok=brsapi_ok_real,
        redis_ok=redis_ok,
        db_ok=db_ok,
        last_snapshot_at=last_snap,
        scheduler_jobs=_scheduled_job_count(),
        telegram_configured=TelegramConfig.from_env().is_configured(),
        active_alert_rules=int(active_rules),
        unread_alerts=int(unread),
    )


def _scheduled_job_count() -> int:
    """تعداد jobهای واقعی GoldDesk (fallback وقتی رجیستری قابل import نیست)."""
    try:
        from brsapi.jobs.gold_desk_jobs import GOLD_DESK_JOBS

        return len(GOLD_DESK_JOBS)
    except Exception:  # noqa: BLE001
        logger.debug("gold job registry unavailable", exc_info=True)
        return 4


@router.get("/freshness", summary="Data-freshness report for every GoldDesk source")
async def get_freshness(session: AsyncSession = Depends(get_db_session)) -> dict:
    """صفحهٔ سلامت داده: آخرین به‌روزرسانی، سن و وضعیت هر منبع در یک پاسخ."""
    report = await build_freshness_report(session)
    report["scheduler_jobs"] = _scheduled_job_count()
    return {"success": True, "data": report}


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
            # دورهٔ out-of-sample: null یعنی برش OOS ممکن نبود (دادهٔ کافی نیست).
            "oos_start": m.oos_start.isoformat() if m.oos_start else None,
            "oos_total_return_pct": m.oos_total_return_pct,
            "oos_buy_hold_return_pct": m.oos_buy_hold_return_pct,
            "oos_alpha_pct": m.oos_alpha_pct,
            "oos_max_drawdown_pct": m.oos_max_drawdown_pct,
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


@anonymous_router.websocket("/ws")
async def gold_websocket(websocket: WebSocket) -> None:
    """WebSocket — پخش زنده snapshot هر ۵ ثانیه.

    Authenticated the same way as ``/ws/market`` (audit API-003): a browser
    cannot attach an ``Authorization`` header to a WebSocket handshake, so the
    access token is read from the ``token`` query parameter. The route lives on
    ``anonymous_router`` because the HTTP auth dependency would reject the
    handshake before this check ever ran.
    """
    from apps.api.endpoints.websocket import verify_websocket_token

    if not await verify_websocket_token(websocket):
        logger.warning("GoldDesk WebSocket rejected: missing or invalid token")
        await websocket.close(code=1008)  # policy violation, before accept
        return

    await ws_endpoint(websocket)


# ── 12. API Tokens (برای استفاده خارجی) ────────────────────


@router.post("/tokens", summary="Generate a new API token")
async def create_token(
    name: str = Query(..., min_length=1, max_length=64),
    scopes: str = Query("read", description="Comma-separated: read,write,admin"),
    _admin: dict = Depends(_require_admin_user),
) -> dict:
    """ساخت token جدید. plain token فقط یک‌بار نمایش داده می‌شود.

    scopes: read (GET) | write (POST/PUT/DELETE) | admin (همه)
    """
    from .api_token import generate_token, save_token

    scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
    valid = {"read", "write", "admin", "metrics"}
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
async def list_api_tokens(_admin: dict = Depends(_require_admin_user)) -> dict:
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
async def delete_token(token_id: str, _admin: dict = Depends(_require_admin_user)) -> dict:
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


def _single_holding_id(h) -> int | None:
    """id یک گروه holding فقط وقتی یک ردیف دارد؛ گروه چندردیفی ``holding_ids`` دارد."""
    ids = tuple(getattr(h, "holding_ids", ()) or ())
    return ids[0] if len(ids) == 1 else None


def _returns_payload(returns) -> dict:
    """سریال‌سازی بازده پورتفوی (اسمی / واقعی / دلاری)."""
    return {
        "nominal_pnl_irt": returns.nominal_pnl_irt,
        "nominal_pnl_pct": returns.nominal_pnl_pct,
        "nominal_xirr": returns.nominal_xirr,
        "real_xirr": returns.real_xirr,
        "usd_xirr": returns.usd_xirr,
        "cpi_basis": returns.cpi_basis,
        "usd_basis": returns.usd_basis,
        "unavailable": returns.unavailable,
    }


@router.get("/portfolio/history", summary="Persisted portfolio value history")
async def get_portfolio_history(
    days: int = Query(90, ge=2, le=730),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """سری ارزش روزانهٔ پرتفوی (جدول ``gold_portfolio_values``)."""
    rows = await load_value_history(session, days=days)
    return {
        "success": True,
        "data": {
            "days": days,
            "points": len(rows),
            "items": [
                {
                    "as_of": r.as_of.isoformat(),
                    "total_value_irt": r.total_value_irt,
                    "total_cost_irt": r.total_cost_irt,
                    "net_flow_irt": r.net_flow_irt,
                    "unpriced_holdings": r.unpriced_holdings,
                }
                for r in rows
            ],
        },
    }


@router.get(
    "/portfolio/performance",
    summary="TWR + risk metrics + benchmark vs gold / USD / TEDPIX",
)
async def get_portfolio_performance(
    days: int = Query(PORTFOLIO_PERFORMANCE_WINDOW_DAYS, ge=2, le=730),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """بازده وزنی‌زمان (TWR) + نوسان/شارپ/افت + مقایسه با طلا، دلار و شاخص کل."""
    snap = await get_hot_snapshot()
    report = await build_performance_report(session, days=days, snapshot=snap)
    return {"success": True, "data": report.as_dict()}


@router.post("/portfolio/snapshot", summary="Persist today's portfolio value")
async def post_portfolio_snapshot(session: AsyncSession = Depends(get_db_session)) -> dict:
    """ثبت فوری ارزش پرتفوی برای امروز (idempotent) — پر کردن تاریخچه بدون انتظار برای scheduler."""
    snap = await get_hot_snapshot()
    row = await capture_portfolio_value(session, snapshot=snap)
    return {
        "success": True,
        "data": {
            "as_of": row.as_of.isoformat(),
            "total_value_irt": row.total_value_irt,
            "total_cost_irt": row.total_cost_irt,
            "net_flow_irt": row.net_flow_irt,
            "unpriced_holdings": row.unpriced_holdings,
        },
    }


@router.get("/portfolio/returns", summary="Portfolio returns (nominal / real / USD)")
async def get_portfolio_returns(session: AsyncSession = Depends(get_db_session)) -> dict:
    """بازده پورتفوی: اسمی (XIRR) + واقعی (تعدیل تورم) + دلاری."""
    snap = await get_hot_snapshot()
    returns = await build_portfolio_returns(session, snapshot=snap)
    return {"success": True, "data": {"returns": _returns_payload(returns)}}


@router.get("/portfolio/tax", summary="Portfolio FIFO cost basis and realized P&L")
async def get_portfolio_tax(session: AsyncSession = Depends(get_db_session)) -> dict:
    """بهای تمام‌شده و سود/زیان تحقق‌یافتهٔ معاملات با روش FIFO."""
    summary = await build_tax_summary(session)
    return {"success": True, "data": summary}


@router.get("/portfolio/export.csv", summary="Export recorded trades as CSV")
async def export_portfolio_trades_csv(session: AsyncSession = Depends(get_db_session)) -> Response:
    """خروجی CSV معاملات ثبت‌شده (برای گزارش و مالیات)."""
    csv_text = await build_trades_csv(session)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="gold_trades.csv"'},
    )


@router.get("/portfolio", summary="Get portfolio summary with P&L")
async def get_portfolio(session: AsyncSession = Depends(get_db_session)) -> dict:
    """خلاصه portfolio با P&L بر اساس قیمت‌های فعلی از snapshot."""
    snap = await get_hot_snapshot()
    prices = get_current_prices(snap)
    summary = await get_holdings_grouped(session, prices)
    returns = await build_portfolio_returns(session, snapshot=snap)
    return {
        "success": True,
        "data": {
            "total_cost": summary.total_cost,
            "total_value": summary.total_value,
            "total_pnl": summary.total_pnl,
            "total_pnl_pct": summary.total_pnl_pct,
            "unpriced_holdings": getattr(summary, "unpriced_holdings", 0),
            # مخرج total_pnl_pct فقط هزینهٔ دارایی‌های قیمت‌دار است (C7).
            "priced_cost": getattr(summary, "priced_cost", None),
            "holdings": [
                {
                    "id": _single_holding_id(h),
                    "holding_ids": list(getattr(h, "holding_ids", ())),
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
            "returns": _returns_payload(returns),
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
    force: bool = Query(False, description="حذف سخت فقط با ?force=true"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """حذف دارایی.

    پیش‌فرض: حذف نرم (soft-delete) — ستون ``deleted_at`` تنظیم می‌شود و ردیف
    دارایی و معامله‌های وابسته آن (از طریق FK با ``ondelete="SET NULL"``) سالم
    می‌مانند، بنابراین گزارش مالیاتی (/portfolio/tax) آسیب نمی‌بیند.
    با ``?force=true`` حذف سخت (hard-delete) انجام می‌شود.
    """
    from .models import GoldHoldingModel

    h = await session.get(GoldHoldingModel, holding_id)
    if not h:
        raise HTTPException(404, "holding not found")
    if h.deleted_at is not None and not force:
        # دارایی soft-delete‌شده دیگر قابل حذف/تغییر نیست مگر با force صریح.
        raise HTTPException(
            409,
            "holding is soft-deleted; pass ?force=true to hard-delete it",
        )
    if force:
        await session.delete(h)  # سخت: holding_id معامله‌ها ⇒ SET NULL
    else:
        h.deleted_at = utc_now_naive()  # نرم: ردیف و معامله‌ها باقی می‌مانند
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
    plan.updated_at = utc_now_naive()
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
    try:
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
    except HoldingDeletedError as exc:
        raise HTTPException(409, str(exc)) from exc
    except HoldingNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
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
    with contextlib.suppress(Exception):
        prices = get_current_prices(snap)
        portfolio = await get_holdings_grouped(session, prices)
        portfolio_data = {
            "total_value": portfolio.total_value,
            "total_cost": portfolio.total_cost,
            "total_pnl": portfolio.total_pnl,
            "total_pnl_pct": portfolio.total_pnl_pct,
        }

    patterns_data = None
    with contextlib.suppress(Exception):
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
                {
                    "method": "GET",
                    "path": "/terminal",
                    "scope": "read",
                    "desc": "Phase 1 data terminal",
                },
                {
                    "method": "POST",
                    "path": "/what-if",
                    "scope": "read",
                    "desc": "Preview intrinsic/bubble under manual inputs",
                },
                {
                    "method": "GET",
                    "path": "/tehran-board",
                    "scope": "read",
                    "desc": "Phase 2 Tehran shop/banking board",
                },
                {
                    "method": "GET",
                    "path": "/platforms",
                    "scope": "read",
                    "desc": "Phase 2 platform price comparison (no trading)",
                },
                {
                    "method": "GET",
                    "path": "/returns-matrix?base_currency=IRR",
                    "scope": "read",
                    "desc": "Phase 2 returns matrix (Rial or USD)",
                },
                {
                    "method": "GET",
                    "path": "/fund-map?size_metric=trade_value",
                    "scope": "read",
                    "desc": "Phase 2 gold fund market map",
                },
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
                {"method": "GET", "path": "/metrics", "scope": "metrics", "desc": "Prometheus scrape"},
                {"method": "WS", "path": "/ws", "scope": "read", "desc": "Live WebSocket"},
            ],
        },
    }


# ── 19. Prometheus Metrics ───────────────────────────────────


async def api_key_auth(request: Request) -> None:
    """دروازهٔ /metrics: فقط Bearer API-token دارای scope «metrics».

    JWT session اینجا کاربردی ندارد؛ مسیر برای scraper است. فقط scope
    ``metrics`` پذیرفته می‌شود (``admin`` جای آن را نمی‌گیرد).
    """
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            401,
            "bearer API token with scope 'metrics' required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from .api_token import has_scope, verify_token

    info = await verify_token(token)
    if info is None or not has_scope(info, "metrics"):
        raise HTTPException(
            401,
            "API token is invalid or lacks the 'metrics' scope",
            headers={"WWW-Authenticate": "Bearer"},
        )


# این مسیر روی ``anonymous_router`` است (بدون گیت JWT) چون احراز هویت‌اش
# API-token است، نه session کاربر. بقیهٔ مسیرهای همین ماژول پشت _require_user
# در apps/api/router.py هستند.
@anonymous_router.get(
    "/metrics",
    summary="Prometheus metrics",
    include_in_schema=False,
    dependencies=[Depends(api_key_auth)],
)
async def metrics() -> Response:
    """Prometheus text format برای scrape."""
    return Response(
        content=render_prometheus(),
        media_type="text/plain; version=0.0.4",
    )


# ── 20. Macro & News ───────────────────────────────────────


@router.get("/macro", summary="Macro events affecting gold market")
async def get_macro_events(limit: int = Query(20, ge=1, le=100)) -> dict:
    """رویدادهای کلان اقتصادی (CPI، نرخ بهره، M2، تقاضا) + تأثیر بر طلا.

    بدون رویدادِ واقعی، ضریب و تفسیر ``null`` است و نبودِ داده اعلام می‌شود. «خنثی» یک
    قضاوت است، نه نبودِ قضاوت؛ و رویدادهای نمونهٔ ``get_sample_events`` هرگز از این‌جا
    بیرون نمی‌روند.
    """
    events = await fetch_macro_events()
    items = sorted(events, key=lambda e: e.published_at, reverse=True)[:limit]
    if not items:
        return {
            "success": True,
            "data": {
                "dataAvailable": False,
                "missingBecause": "هیچ رویداد کلانی از منبع واقعی ثبت نشده است؛ scrape CBI/مرکز آمار هنوز داده‌ای ننوشته است.",
                "count": 0,
                "affects_score": False,
                "macro_multiplier": None,
                "interpretation": None,
                "events": [],
            },
        }
    multiplier = compute_macro_multiplier(events)
    return {
        "success": True,
        "data": {
            "dataAvailable": True,
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
    with contextlib.suppress(Exception):
        from core.cache import get_cache

        from .crypto import REDIS_KEY_CRYPTO

        cache = get_cache()
        if not force_refresh:
            raw = await cache.get(REDIS_KEY_CRYPTO)
            if raw:
                import json

                data = json.loads(raw) if isinstance(raw, str) else raw
                return {"success": True, "data": data}

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

    with contextlib.suppress(Exception):
        import json

        from core.cache import get_cache

        from .crypto import REDIS_KEY_CRYPTO

        cache = get_cache()
        await cache.set(REDIS_KEY_CRYPTO, json.dumps(result, default=str), ttl=300)

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
