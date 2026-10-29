"""GoldDesk Scheduler Jobs — 6 job.

- gold_snapshot: هر 5 دقیقه snapshot + ذخیره DB
- gold_score_persist: هر 5 دقیقه امتیاز
- gold_alert_evaluate: هر 2 دقیقه بررسی قوانین (شامل قوانین ریسک پرتفوی)
- gold_fund_nav: هر شب 21:05 ذخیره NAV/حباب صندوق‌ها
- gold_portfolio_value: هر شب 21:10 ثبت ارزش روزانهٔ پرتفوی (تاریخچهٔ TWR)
- gold_daily_history: هر شب 21:00 backfill historical bubble
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.jobs.registry import BrsApiSyncJob
from core.cache import get_cache
from core.database import get_session
from core.logging import get_logger
from src.gold_desk import snapshot_service
from src.gold_desk.alert_engine import evaluate_rules
from src.gold_desk.constants import REDIS_KEY_SNAPSHOT
from src.gold_desk.models import GoldFundNAVModel, GoldScoreHistoryModel, GoldSnapshotModel
from src.gold_desk.schemas import SnapshotResponse

logger = get_logger(__name__)


# ── Job 1: Snapshot ────────────────────────────────────────────


async def _persist_snapshot(session: AsyncSession, snap: SnapshotResponse) -> None:
    """ذخیره snapshot در DB و Redis."""
    now = snap.snapshot_at
    refs = snap.references
    rows: list[dict[str, Any]] = []

    for asset_type, assets in (("gold", snap.gold), ("coin", snap.coins)):
        for _k, a in assets.items():
            rows.append(
                {
                    "symbol": a.symbol,
                    "display_name": a.display_name,
                    "asset_type": asset_type,
                    "market_price": a.market_price,
                    "fair_value": a.fair_value,
                    "bubble_abs": a.bubble_abs,
                    "bubble_pct": a.bubble_pct,
                    "implied_usd": a.implied_usd,
                    "xau_usd": refs.xau_usd,
                    "usd_irt": refs.usd_irt,
                    "aed_irt": refs.aed_irt,
                    "aed_parity_usd": refs.aed_parity_usd,
                    "aed_gap_pct": refs.aed_gap_pct,
                    "quality_flag": a.quality_flag,
                    "snapshot_at": now,
                }
            )

    if rows:
        session.add_all([GoldSnapshotModel(**r) for r in rows])
        await session.commit()
        logger.info("gold_snapshot: persisted %d rows", len(rows))


async def job_gold_snapshot(force: bool = False) -> None:
    """ساخت snapshot + ذخیره + cache + WebSocket broadcast."""
    start = time.monotonic()
    try:
        async for session in get_session():
            snap = await snapshot_service.build_snapshot(session)
            await _persist_snapshot(session, snap)
            snap_dict = snap.model_dump(mode="json")
            cache = get_cache()
            await cache.set(
                REDIS_KEY_SNAPSHOT,
                json.dumps(snap_dict, default=str),
                ttl=600,
            )
            # Live signals: مقایسه با snapshot قبلی
            try:
                from src.gold_desk.live_signals import detect_and_broadcast

                signals = await detect_and_broadcast(snap_dict)
                if signals:
                    logger.info("live_signals: %d new signals", len(signals))
            except Exception as sig_exc:
                logger.debug("live signals failed: %s", sig_exc)

            # رویداد آماده‌بودن snapshot را در Redis منتشر کن؛ این process
            # کلاینت WebSocket ندارد، پس broadcast محلی بی‌اثر بود.
            from src.gold_desk.ws_hub import publish_ws_event

            await publish_ws_event(
                {"type": "snapshot_ready", "as_of": snap.snapshot_at.isoformat()}
            )
            # Publish canonical quote events to the shared WebSocket +
            # Redis Pub/Sub channel used by the multi-asset dashboard. The
            # GoldDesk snapshot_ready event was published above.
            try:
                from services.realtime_service import get_realtime_service

                realtime = get_realtime_service()
                for asset_group in (snap.gold, snap.coins):
                    for asset in asset_group.values():
                        await realtime.publish_price(
                            asset.symbol,
                            {
                                "price": asset.market_price,
                                "change_percent": asset.bubble_pct or 0,
                                "bubble_pct": asset.bubble_pct,
                                "fair_value": asset.fair_value,
                                "timestamp": snap.snapshot_at.isoformat(),
                                "source": "gold_snapshot",
                            },
                        )
            except Exception as rt_exc:
                logger.debug("Shared realtime publish skipped: %s", rt_exc)
            elapsed = (time.monotonic() - start) * 1000
            logger.info(
                "gold_snapshot: OK in %.0fms (score=%d)",
                elapsed,
                snap.score.total,
            )
            break
    except Exception as exc:
        # Surface the failure to the caller (``_run_direct_job`` turns an
        # exception into ``success=False``). Swallowing it here made every
        # DB/snapshot error look like a green job on the scheduler.
        logger.exception("gold_snapshot failed: %s", exc)
        raise


# ── Job 2: Score Persist ───────────────────────────────────────


async def job_gold_score_persist(force: bool = False) -> None:
    """ذخیره امتیاز فعلی در gold_score_history."""
    try:
        async for session in get_session():
            snap = await snapshot_service.build_snapshot(session)
            components_json = json.dumps(
                {
                    "bubble": snap.score.components.bubble,
                    "nav": snap.score.components.nav,
                    "tsetmc": snap.score.components.tsetmc,
                    "technical": snap.score.components.technical,
                    "parity": snap.score.components.parity,
                    "fund_flow": snap.score.components.fund_flow,
                }
            )
            row = GoldScoreHistoryModel(
                total_score=snap.score.total,
                components_json=components_json,
                decision=snap.score.decision,
                hard_stop_active=snap.score.hard_stop_active,
                hard_stop_reason=snap.score.hard_stop_reason,
            )
            session.add(row)
            await session.commit()
            logger.info("gold_score_persist: score=%d", snap.score.total)
            break
    except Exception as exc:
        logger.exception("gold_score_persist failed: %s", exc)
        raise


# ── Job 3: Alert Evaluation ─────────────────────────────────────


async def _portfolio_risk_metrics(session: AsyncSession) -> dict[str, float | None]:
    """معیارهای ریسک پرتفوی برای قوانین هشدار (تمرکز/انحراف/افت/TWR).

    در نبود تاریخچه یا داده، دیکشنری خالی برمی‌گردد ⇒ قوانین پرتفوی ارزیابی
    نمی‌شوند (هیچ هشدار کاذبی ساخته نمی‌شود).
    """
    try:
        from src.gold_desk.portfolio_history import build_performance_report

        report = await build_performance_report(session, include_benchmarks=False)
        return report.risk_metrics()
    except Exception as exc:  # noqa: BLE001
        logger.warning("portfolio risk metrics unavailable: %s", exc)
        return {}


async def job_gold_alert_evaluate(force: bool = False) -> None:
    """بررسی قوانین + dispatch (شامل قوانین مبتنی بر معیارهای ریسک پرتفوی)."""
    try:
        async for session in get_session():
            snap = await snapshot_service.build_snapshot(session)
            metrics = await _portfolio_risk_metrics(session)
            events = await evaluate_rules(session, snap, portfolio_metrics=metrics)
            if events:
                logger.info("gold_alert_evaluate: %d events fired", len(events))
            else:
                logger.debug("gold_alert_evaluate: no events")
            break
    except Exception as exc:
        logger.exception("gold_alert_evaluate failed: %s", exc)
        raise


# ── Job 4: Fund NAV Persist ─────────────────────────────────────


async def _persist_fund_nav(session: AsyncSession, snap: SnapshotResponse) -> int:
    """Upsert روزانهٔ NAV/حباب صندوق‌ها در ``gold_fund_nav`` (کلید نماد+تاریخ)."""
    funds = list(snap.funds or [])
    if not funds:
        return 0
    when = snap.snapshot_at
    day = datetime(when.year, when.month, when.day)
    written = 0
    for f in funds:
        market_price = (
            float(f.market_price) if f.market_price is not None else None
        )
        nav = float(f.nav_per_unit) if f.nav_per_unit is not None else None
        if market_price is None or nav is None or market_price <= 0 or nav <= 0:
            # A fund without a traded price has no P/NAV observation.  Writing
            # 0/0 here used to turn every missing quote into a fake 0% premium.
            logger.debug(
                "fund_nav skipped %s: market_price=%r nav=%r date=%s",
                getattr(f, "symbol", None),
                market_price,
                nav,
                day,
            )
            continue
        row = (
            await session.execute(
                select(GoldFundNAVModel).where(
                    GoldFundNAVModel.symbol == f.symbol, GoldFundNAVModel.date == day
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = GoldFundNAVModel(symbol=f.symbol, fund_name=f.fund_name, date=day)
            session.add(row)
        row.fund_name = f.fund_name
        row.nav_per_unit = nav
        row.market_price = market_price
        row.bubble_abs = market_price - nav
        row.bubble_pct = (market_price - nav) / nav * 100.0
        row.real_buy_value = int(f.real_buy_value or 0)
        row.real_sell_value = int(f.real_sell_value or 0)
        row.bpr = float(f.bpr or 0.0)
        written += 1
    await session.commit()
    return written


async def job_gold_fund_nav(force: bool = False) -> None:
    """ذخیره NAV/حباب صندوق‌های طلا برای امروز."""
    try:
        async for session in get_session():
            snap = await snapshot_service.build_snapshot(session)
            written = await _persist_fund_nav(session, snap)
            logger.info("gold_fund_nav: persisted %d fund rows", written)
            break
    except Exception as exc:
        logger.exception("gold_fund_nav failed: %s", exc)
        raise


# ── Job 5: Portfolio Value Snapshot ─────────────────────────────


async def job_gold_portfolio_value(force: bool = False) -> None:
    """ثبت ارزش روزانهٔ پرتفوی (پایهٔ TWR و مقایسه با بنچمارک)."""
    try:
        from src.gold_desk.portfolio_history import capture_portfolio_value

        async for session in get_session():
            snap = await snapshot_service.build_snapshot(session)
            row = await capture_portfolio_value(
                session, snapshot=snap.model_dump(mode="json")
            )
            logger.info(
                "gold_portfolio_value: as_of=%s value=%.0f cost=%.0f flow=%.0f",
                row.as_of,
                row.total_value_irt,
                row.total_cost_irt,
                row.net_flow_irt,
            )
            break
    except Exception as exc:
        logger.exception("gold_portfolio_value failed: %s", exc)
        raise


# ── Job 6: Daily History Backfill ─────────────────────────────


async def job_gold_daily_history(force: bool = False) -> None:
    """Placeholder: daily historical-bubble backfill is NOT implemented yet.

    Kept registered and callable for on-demand use, but disabled in the
    schedule (see ``GOLD_DESK_JOBS``): a function job that returns normally is
    reported as ``success=True`` by ``_run_direct_job``, so scheduling this
    no-op would show a green nightly job that writes nothing.
    """
    logger.warning(
        "gold_daily_history: NOT IMPLEMENTED — no historical backfill performed"
    )


# ── Job descriptors ───────────────────────────────────────────


GOLD_DESK_JOBS: list[BrsApiSyncJob] = [
    BrsApiSyncJob(
        name="gold_snapshot",
        endpoint_config=None,  # type: ignore — direct function call
        cron=300,  # هر 5 دقیقه
        description="Build gold market snapshot + persist to DB + cache in Redis",
    ),
    BrsApiSyncJob(
        name="gold_score_persist",
        endpoint_config=None,  # type: ignore
        cron=300,
        description="Persist current decision score to history",
    ),
    BrsApiSyncJob(
        name="gold_alert_evaluate",
        endpoint_config=None,  # type: ignore
        cron=120,  # هر 2 دقیقه
        description="Evaluate alert rules and fire events",
    ),
    BrsApiSyncJob(
        name="gold_daily_history",
        endpoint_config=None,  # type: ignore
        cron="0 21 * * *",  # هر شب 21:00
        enabled=False,
        description="(DISABLED) Daily historical bubble backfill — placeholder, not implemented",
    ),
    BrsApiSyncJob(
        name="gold_fund_nav",
        endpoint_config=None,  # type: ignore
        cron="5 21 * * *",  # هر شب 21:05
        description="Persist daily gold fund NAV + P/NAV bubble rows",
    ),
    BrsApiSyncJob(
        name="gold_portfolio_value",
        endpoint_config=None,  # type: ignore
        cron="10 21 * * *",  # هر شب 21:10
        description="Persist daily portfolio value snapshot (TWR / benchmark base)",
    ),
]


# نگاشت نام job → تابع اجرا.
# این jobها ``endpoint_config=None`` دارند (فراخوانی مستقیم تابع)، پس رجیستری
# عمومی BrsApi برای اجرای آن‌ها به این نگاشت نیاز دارد.
GOLD_DESK_JOB_FUNCTIONS: dict[str, Any] = {
    "gold_snapshot": job_gold_snapshot,
    "gold_score_persist": job_gold_score_persist,
    "gold_alert_evaluate": job_gold_alert_evaluate,
    "gold_fund_nav": job_gold_fund_nav,
    "gold_portfolio_value": job_gold_portfolio_value,
    "gold_daily_history": job_gold_daily_history,
}
