"""GoldDesk Scheduler Jobs — 4 job.

- gold_snapshot: هر 5 دقیقه snapshot + ذخیره DB
- gold_score_persist: هر 5 دقیقه امتیاز
- gold_alert_evaluate: هر 2 دقیقه بررسی قوانین
- gold_daily_history: هر شب 21:00 backfill historical bubble
"""

from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.jobs.registry import BrsApiSyncJob
from core.cache import get_cache
from core.database import get_session
from core.logging import get_logger
from src.gold_desk import snapshot_service
from src.gold_desk.alert_engine import evaluate_rules
from src.gold_desk.constants import REDIS_KEY_SNAPSHOT
from src.gold_desk.models import GoldScoreHistoryModel, GoldSnapshotModel
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

            # WebSocket broadcast
            try:
                from src.gold_desk.ws_hub import get_hub

                hub = get_hub()
                hub.cache_snapshot(snap_dict)
                await hub.broadcast({"type": "snapshot", "data": snap_dict})
            except Exception as ws_exc:
                logger.debug("WS broadcast skipped: %s", ws_exc)
            # Publish canonical quote events to the shared WebSocket +
            # Redis Pub/Sub channel used by the multi-asset dashboard. The
            # dedicated GoldDesk hub above remains available for consumers
            # that need the complete snapshot payload.
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
                "gold_snapshot: OK in %.0fms (score=%d, ws_clients=%d)",
                elapsed,
                snap.score.total,
                get_hub().client_count(),
            )
            break
    except Exception as exc:
        logger.exception("gold_snapshot failed: %s", exc)


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


# ── Job 3: Alert Evaluation ─────────────────────────────────────


async def job_gold_alert_evaluate(force: bool = False) -> None:
    """بررسی قوانین + dispatch."""
    try:
        async for session in get_session():
            snap = await snapshot_service.build_snapshot(session)
            events = await evaluate_rules(session, snap)
            if events:
                logger.info("gold_alert_evaluate: %d events fired", len(events))
            else:
                logger.debug("gold_alert_evaluate: no events")
            break
    except Exception as exc:
        logger.exception("gold_alert_evaluate failed: %s", exc)


# ── Job 4: Daily History Backfill ─────────────────────────────


async def job_gold_daily_history(force: bool = False) -> None:
    """Backfill روزانه historical bubble (می‌تواند empty باشد اگه BrsApi history موجود نیست)."""
    logger.info("gold_daily_history: started (placeholder — no-op)")


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
        description="Daily backfill of historical bubble data",
    ),
]
