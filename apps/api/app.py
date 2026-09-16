from __future__ import annotations

import asyncio
import traceback
from collections import deque
from collections.abc import AsyncGenerator, Coroutine
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse

from apps.api.error_handlers import register_error_handlers
from apps.api.metrics import MetricsMiddleware, get_prometheus_exporter
from apps.api.middleware import (
    CSRFMiddleware,
    InputSanitizationMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityMiddleware,
    TimingMiddleware,
)
from apps.api.router import Router
from core.cache import get_cache
from core.config import settings
from core.database import close_database, get_session, init_database
from core.logging import get_logger, setup_logging
from ml.models import register_all_models

try:
    from apps.api.dependencies import require_roles
except Exception:  # pragma: no cover
    require_roles = None  # type: ignore

logger = get_logger(__name__)


# Every long-lived coroutine started by the API is registered here. Keeping a
# strong reference prevents silent task failures and lets lifespan cancel and
# await all work before closing Redis/DB connections.
_background_tasks: set[asyncio.Task[Any]] = set()


def _track_background_task(coro: Coroutine[Any, Any, Any], name: str) -> asyncio.Task[Any]:
    task = asyncio.create_task(coro, name=name)
    _background_tasks.add(task)

    def _done(completed: asyncio.Task[Any]) -> None:
        _background_tasks.discard(completed)
        if completed.cancelled():
            return
        try:
            error = completed.exception()
        except asyncio.CancelledError:
            return
        if error is not None:
            logger.error(
                "Background task %s failed: %s",
                name,
                error,
                exc_info=(type(error), error, error.__traceback__),
            )

    task.add_done_callback(_done)
    return task


async def _stop_background_tasks() -> None:
    """Cancel and await API-owned background tasks before dependencies close."""
    tasks = list(_background_tasks)
    if not tasks:
        return
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    _background_tasks.clear()


# ── Notification callback for rate limit alerts ──


async def _rate_limit_notify(message: str) -> None:
    """Send rate limit alerts via Telegram if configured, always log."""
    logger.warning("RATE LIMIT ALERT: %s", message)
    with suppress(Exception):
        from integrations.notifications.telegram_sender import TelegramSender

        sender = TelegramSender()
        result = await sender.send(f"⚠️ <b>BrsApi Rate Limit</b>\n\n{message}")
        if not result.success:
            logger.debug("Telegram notification not sent (not configured?): %s", result.error)


# ── Orchestrator hourly cron state ──
# In-memory working copy (fast path + fallback when Redis is unavailable).
# When Redis is connected the state is mirrored there via set_persistent so
# multiple API workers observe the same state (multi-worker safe).

_cron_state: dict = {
    "last_run": None,
    "last_signal_count": 0,
    "last_accuracy": {},
    "last_retrain_count": 0,
    "last_error": None,
    "run_count": 0,
    "enabled": True,
    "history": deque(maxlen=100),
}

# Alert dedup: stores timestamp (time.time()) of last alert sent per type.
# Re-alert blocked if less than 6 hours since the last alert.
ALERT_COOLDOWN_S = 6 * 3600
_alert_state: dict[str, float] = {
    "consecutive_failures": 0.0,
    "accuracy_drop": 0.0,
    "was_in_failure_streak": 0.0,  # timestamp when streak started; 0 = not in streak
    "was_accuracy_below_50": 0.0,  # timestamp when accuracy first dropped; 0 = healthy
}

_CRON_STATE_KEY = "orchestrator:cron_state"
_ALERT_STATE_KEY = "orchestrator:alert_state"


async def _load_cron_state_from_store() -> None:
    """Hydrate ``_cron_state``/``_alert_state`` from Redis when connected.

    Multi-worker sync: every worker picks up the latest persisted state
    (e.g. a toggle made on another worker, or history appended by the cron
    process). Mutates the module dicts in place so callers keep their
    references. No-op when Redis is unavailable (in-memory fallback).
    """
    cache = get_cache()
    if not cache.is_connected:
        return
    try:
        raw = await cache.get(_CRON_STATE_KEY)
        if isinstance(raw, dict):
            raw["history"] = deque(raw.get("history", []), maxlen=100)
            _cron_state.clear()
            _cron_state.update(raw)
        raw_alert = await cache.get(_ALERT_STATE_KEY)
        if isinstance(raw_alert, dict):
            _alert_state.clear()
            _alert_state.update(raw_alert)
    except Exception:
        logger.debug("Cron state load from Redis failed", exc_info=True)


async def _save_cron_state_to_store() -> None:
    """Persist ``_cron_state``/``_alert_state`` to Redis when connected.

    ``history`` is a ``deque`` — converted to a list so it round-trips
    through JSON. No-op when Redis is unavailable.
    """
    cache = get_cache()
    if not cache.is_connected:
        return
    try:
        payload = dict(_cron_state)
        payload["history"] = list(_cron_state["history"])
        await cache.set_persistent(_CRON_STATE_KEY, payload)
        await cache.set_persistent(_ALERT_STATE_KEY, dict(_alert_state))
    except Exception:
        logger.debug("Cron state save to Redis failed", exc_info=True)


async def _send_cron_alert(title: str, message: str, icon: str = "🔴") -> None:
    """Send a cron alert via Telegram (if configured) and always log."""
    logger.warning("CRON ALERT [%s]: %s", title, message)
    with suppress(Exception):
        from integrations.notifications.telegram_sender import TelegramSender

        sender = TelegramSender()
        result = await sender.send(f"{icon} <b>Cron Alert: {title}</b>\n\n{message}")
        if not result.success:
            logger.debug("Telegram alert not sent (not configured?): %s", result.error)


async def _check_cron_alerts() -> None:
    """Check cron history for alert conditions: 3 consecutive failures or accuracy < 50%.

    Uses _alert_state timestamps for cooldown and recovery tracking.
    """
    history = list(_cron_state["history"])
    if len(history) < 3:
        return

    import time

    now_ts = time.time()

    latest = history[-1]
    latest_ok = latest.get("success", False)

    # ═══ 1. Three consecutive failures ═══
    last_three = history[-3:]
    all_failed = all(not h.get("success", True) for h in last_three)

    if all_failed:
        # Mark that we entered a failure streak
        if _alert_state["was_in_failure_streak"] == 0.0:
            _alert_state["was_in_failure_streak"] = now_ts

        if (now_ts - _alert_state["consecutive_failures"]) >= ALERT_COOLDOWN_S:
            errors = [h.get("error", "Unknown")[:100] for h in last_three]
            await _send_cron_alert(
                "3 شکست متوالی کرون",
                f"کرون orchestrator در ۳ اجرای متوالی شکست خورده است.\n"
                f"آخرین خطا: {errors[-1]}\n"
                f"اجراهای: {last_three[0]['run']}، {last_three[1]['run']}، {last_three[2]['run']}\n"
                f"زمان آخرین شکست: {last_three[-1].get('timestamp', '?')}",
            )
            _alert_state["consecutive_failures"] = now_ts
        return  # Don't send multiple alert types in the same check

    # ── Recovery: cron succeeded after a failure streak ──
    if latest_ok and _alert_state["was_in_failure_streak"] > 0.0:
        streak_duration = now_ts - _alert_state["was_in_failure_streak"]
        await _send_cron_alert(
            "بازیابی کرون",
            f"کرون orchestrator پس از شکست‌های متوالی با موفقیت اجرا شد.\n"
            f"مدت زمان اختلال: {streak_duration / 60:.0f} دقیقه\n"
            f"شماره اجرای موفق: {latest.get('run', '?')}\n"
            f"سیگنال‌های تولیدشده: {latest.get('signals', 0)}\n"
            f"زمان بازیابی: {latest.get('timestamp', '?')}",
            icon="🟢",
        )
        _alert_state["was_in_failure_streak"] = 0.0
        _alert_state["consecutive_failures"] = 0.0

    # ═══ 2. Overall accuracy dropped below 50% ═══
    if latest_ok:
        acc = latest.get("accuracy", 100)

        if acc < 50:
            # Mark that accuracy is in trouble
            if _alert_state["was_accuracy_below_50"] == 0.0:
                _alert_state["was_accuracy_below_50"] = now_ts

            if (now_ts - _alert_state["accuracy_drop"]) >= ALERT_COOLDOWN_S:
                await _send_cron_alert(
                    "کاهش دقت کل به زیر ۵۰٪",
                    f"دقت کل سیگنال‌ها به {acc:.1f}٪ کاهش یافته است (زیر آستانه ۵۰٪).\n"
                    f"سیگنال‌های آخرین اجرا: {latest.get('signals', 0)}\n"
                    f"زمان اجرا: {latest.get('timestamp', '?')}\n"
                    f"بازآموزی خودکار در اجرای بعدی فعال خواهد شد.",
                )
                _alert_state["accuracy_drop"] = now_ts

        # ── Recovery: accuracy climbed back above 50% ──
        elif acc >= 50 and _alert_state["was_accuracy_below_50"] > 0.0:
            await _send_cron_alert(
                "بازگشت دقت به بالای ۵۰٪",
                f"دقت کل سیگنال‌ها به {acc:.1f}٪ بازگشته است (بالای آستانه ۵۰٪).\n"
                f"شماره اجرا: {latest.get('run', '?')}\n"
                f"سیگنال‌های تولیدشده: {latest.get('signals', 0)}\n"
                f"زمان بازیابی: {latest.get('timestamp', '?')}",
                icon="🟢",
            )
            _alert_state["was_accuracy_below_50"] = 0.0
            _alert_state["accuracy_drop"] = 0.0


async def _orchestrator_hourly_cron() -> None:
    """Background task: run the quant signal orchestrator every hour.

    This closes the feedback loop:
      generate signals -> persist -> evaluate outcomes -> retrain if needed

    Each run produces signals, records outcomes for past signals, and
    auto-retrains models when accuracy drops below threshold.
    Over time, this drives the system toward >70% accuracy.
    """
    from datetime import UTC, datetime

    from services.quant_signal_orchestrator import QuantSignalOrchestrator

    loop = asyncio.get_running_loop()

    while True:
        try:
            # Multi-worker sync: pick up toggles/history written by other
            # workers (or by the manual run-now endpoint) before this tick.
            await _load_cron_state_from_store()

            if not _cron_state["enabled"]:
                await asyncio.sleep(60)
                continue

            tick_start = loop.time()

            logger.info("=" * 50)
            logger.info("HOURLY ORCHESTRATOR CRON — run #%d", _cron_state["run_count"] + 1)
            logger.info("=" * 50)

            orchestrator = QuantSignalOrchestrator()
            report = await orchestrator.generate(
                market_filter="all",
                timeframe_filter="all",
                min_confidence=0.35,
                limit=100,
                use_ml=True,
                use_voting=True,
                use_confidence_calibration=True,
            )

            d = report.to_dict()
            signals = d.get("signals", [])
            accuracy = d.get("accuracy", {})
            retrain = d.get("retrain", [])

            _cron_state["last_run"] = datetime.now(UTC).isoformat()
            _cron_state["last_signal_count"] = len(signals)
            _cron_state["last_accuracy"] = accuracy or {}
            _cron_state["last_retrain_count"] = len(retrain)
            _cron_state["last_error"] = None
            _cron_state["run_count"] += 1
            _cron_state["history"].append(
                {
                    "run": _cron_state["run_count"],
                    "timestamp": _cron_state["last_run"],
                    "signals": len(signals),
                    "accuracy": accuracy.get("overall", 0),
                    "retrain_count": len(retrain),
                    "success": True,
                }
            )

            logger.info(
                "Cron run #%d complete: %d signals, %.0f%% overall accuracy, %d markets retrained",
                _cron_state["run_count"],
                len(signals),
                accuracy.get("overall", 0),
                len(retrain),
            )

            if retrain:
                for rr in retrain:
                    logger.info(
                        "  [RETRAIN] %s: %s | %.1f%% -> %.1f%%",
                        rr.get("market", "?"),
                        rr.get("trigger", "?"),
                        rr.get("old_accuracy_pct", 0),
                        rr.get("new_accuracy_pct", 0),
                    )

            # Check alerts after successful run
            await _check_cron_alerts()
            await _save_cron_state_to_store()

        except Exception:
            logger.exception("Hourly orchestrator cron failed")
            _cron_state["last_error"] = str(traceback.format_exc())[:500]
            _cron_state["last_run"] = datetime.now(UTC).isoformat()
            _cron_state["run_count"] += 1
            _cron_state["history"].append(
                {
                    "run": _cron_state["run_count"],
                    "timestamp": _cron_state["last_run"],
                    "signals": 0,
                    "accuracy": 0,
                    "retrain_count": 0,
                    "success": False,
                    "error": _cron_state["last_error"][:200],
                }
            )

            # Check alerts after failed run
            await _check_cron_alerts()
            await _save_cron_state_to_store()

        # Wait 1 hour before next run (drift-corrected)
        elapsed = loop.time() - tick_start
        sleep_seconds = max(0, 3600 - elapsed)
        logger.debug("Cron run took %.1fs — sleeping %.1fs until next tick", elapsed, sleep_seconds)
        await asyncio.sleep(sleep_seconds)


# ── Startup background tasks ──

# Distributed-lock ownership registry for startup tasks (key → owner token).
_startup_lock_owners: dict[str, str] = {}

# Shared lock instance: the in-memory fallback keeps per-instance state, so a
# single instance must be reused across acquire/release calls.
_startup_locker = None  # lazy JobLocking singleton


def _get_startup_locker():
    global _startup_locker
    if _startup_locker is None:
        try:
            from jobs.locking import JobLocking

            _startup_locker = JobLocking(default_ttl=600)
        except Exception:
            _startup_locker = None
    return _startup_locker


async def _with_startup_lock(key: str, task: str) -> bool:
    """Acquire a distributed lock for a startup DB task.

    With multiple API workers (or an API + scheduler running side by side),
    startup tasks such as the full BrsApi sync or the Decision Engine seed
    could otherwise run concurrently and race on the same tables. The lock is
    Redis-backed (auto-expiring, owner-checked via ``JobLocking``) with an
    in-memory fallback — returns ``False`` when another process already owns
    it, so the caller skips its work instead of duplicating writes.

    Returns True when the lock was acquired (caller must ``release``).
    """
    import os
    import socket
    import uuid

    locker = _get_startup_locker()
    if locker is None:
        logger.warning("Startup lock unavailable for %s — running without lock", task)
        return True

    owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    lock_key = f"startup:{key}"
    acquired = await locker.acquire(lock_key, owner, ttl=600)
    if not acquired:
        logger.info("Startup task %s skipped — another process is already running it", task)
        return False

    # Stash the owner so the caller can release this exact lock.
    _startup_lock_owners[lock_key] = owner
    return True


async def _release_startup_lock(key: str) -> None:
    locker = _get_startup_locker()
    if locker is None:
        return
    lock_key = f"startup:{key}"
    owner = _startup_lock_owners.pop(lock_key, None)
    if owner:
        await locker.release(lock_key, owner)


async def _decision_engine_startup_seed() -> None:
    """Background task: auto-seed Decision Engine architecture data on API startup.

    Merges all 5 JSON files (architecture, features, services, database, api)
    into the decision_architectures table if it's empty. Non-blocking.
    Guarded by a distributed lock so multiple workers don't seed in parallel.
    """
    if not await _with_startup_lock("decision_seed", "decision-seed"):
        return
    try:
        from apps.api.endpoints.decision_engine import _auto_seed

        logger.info("Decision Engine — auto-seeding architecture data on startup...")
        session_obtained = False
        async for session in get_session():
            session_obtained = True
            await _auto_seed(session)
            logger.info("Decision Engine — startup auto-seed complete")
            break
        if not session_obtained:
            logger.warning("Decision Engine — could not obtain DB session for auto-seed")
    except Exception:
        logger.exception("Decision Engine — startup auto-seed failed")
    finally:
        await _release_startup_lock("decision_seed")


async def _fund_sync_cron() -> None:
    """
    Background task: sync fund data from BrsApi every 15 minutes during market hours.

    Runs at market-open pace (every 15 min) while the market is open,
    and falls back to once per day (02:00 Tehran) outside market hours
    for end-of-day NAV updates.

    The sync respects BrsApi rate limits via a per-symbol delay. Execution
    is sequential because FundService/BrsApiQueryService share one
    AsyncSession (not concurrency-safe).
    """
    from services.fund_sync_service import FundSyncService, _is_market_open, _next_market_open_delay

    while True:
        try:
            # Lazy imports to avoid circular imports at module level
            from brsapi.services.query_service import BrsApiQueryService
            from core.database import async_session_factory
            from services.fund_service import FundService

            if async_session_factory is None:
                logger.warning("Fund sync: DB not available, retrying in 60s")
                await asyncio.sleep(60)
                continue

            async with async_session_factory() as session:
                fund_service = FundService(session=session)
                brsapi = BrsApiQueryService(session=session)
                sync_service = FundSyncService(
                    fund_service=fund_service,
                    brsapi=brsapi,
                )

                report = await sync_service.sync_all_funds()
                logger.info(
                    "Fund sync cycle: %s — next sync in %s",
                    report.summary,
                    "15 min (market open)" if _is_market_open() else "~24h (market closed)",
                )

                # Log failed symbols for monitoring
                if report.errors:
                    for err in report.errors[:5]:  # First 5 only
                        logger.warning("  Fund sync error: %s — %s", err["symbol"], err["error"])

        except Exception:
            logger.exception("Fund sync cron failed — retrying in 60s")
            await asyncio.sleep(60)
            continue

        # ── Next interval ──
        if _is_market_open():
            await asyncio.sleep(15 * 60)  # Every 15 min during market hours
        else:
            # Outside market hours: wait until next market open
            delay = _next_market_open_delay()
            logger.info("Market closed — next fund sync at market open (in %.0f min)", delay / 60)
            await asyncio.sleep(min(delay, 3600))  # Check at least every hour


async def _ml_model_preload() -> None:
    """Background task: warm the ModelLoader LRU cache for active symbols.

    Loads ML models for the union of the active Watchlist and Smart Screener
    symbols into the LRU cache so the first signal-generation run after
    startup doesn't pay a cold disk-load penalty. Symbols without a trained
    artifact are skipped silently by ``ModelLoader.preload()``.

    Non-blocking and defensive: a missing DB table, a failed query, or any
    other error is logged but never crashes startup. No distributed lock is
    needed — ``preload`` is read-only and idempotent (each worker warms its
    own in-memory cache).
    """
    try:
        from sqlalchemy import text

        from ml.model_loader import get_model_loader

        loader = get_model_loader()
        session_obtained = False

        async for session in get_session():
            session_obtained = True
            watchlist_symbols: list[str] = []
            screener_symbols: list[str] = []

            # 1. Active Watchlist symbols
            try:
                r = await session.execute(
                    text("SELECT symbol FROM watchlist WHERE symbol IS NOT NULL AND symbol != ''")
                )
                watchlist_symbols = [row[0] for row in r.fetchall()]
            except Exception:
                logger.debug("ML preload: watchlist query failed (table missing?)", exc_info=True)

            # 2. Active Smart Screener symbols (same universe as Screener110)
            try:
                r = await session.execute(
                    text(
                        "SELECT symbol FROM symbols "
                        "WHERE (is_active = TRUE OR is_active IS NULL) "
                        "AND symbol IS NOT NULL AND symbol != ''"
                    )
                )
                screener_symbols = [row[0] for row in r.fetchall()]
            except Exception:
                logger.debug("ML preload: screener symbols query failed", exc_info=True)

            # Union, preserving order, dedup.
            # Order matters for LRU retention: ModelLoader.preload() loads in
            # list order and keeps only the LAST ~20 models hot, so the most
            # important (watchlist) symbols must come last to stay resident.
            symbols = list(dict.fromkeys(screener_symbols + watchlist_symbols))
            if not symbols:
                logger.info("ML model preload: no active symbols found — skipping")
                break

            report = await loader.preload(symbols=symbols)
            logger.info(
                "ML model preload complete: %d loaded, %d missing (%d watchlist + %d screener symbols)",
                report.get("loaded", 0),
                len(report.get("missing", [])),
                len(watchlist_symbols),
                len(screener_symbols),
            )
            break

        if not session_obtained:
            logger.warning("ML model preload: could not obtain DB session — skipping")
    except Exception:
        logger.exception("ML model preload failed (non-fatal)")


async def _fetch_news_on_startup() -> None:
    """Background task: fetch news from RSS feeds on API startup.

    Retries up to 3 times with exponential backoff (15s, 30s, 60s) on failure.
    Guarded by a distributed lock so only one worker ingests news at boot.
    """
    if not await _with_startup_lock("news_ingest", "news-ingest"):
        return
    MAX_RETRIES = 3
    BASE_DELAY = 15  # seconds

    try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                from services.news_ingestion import NewsIngestionService

                logger.info("Auto-fetching news on startup (attempt %d/%d)...", attempt, MAX_RETRIES)
                session_obtained = False
                async for session in get_session():
                    session_obtained = True
                    service = NewsIngestionService(session=session)
                    stats = await service.ingest(
                        sources=None,
                        limit_per_source=30,
                        save=True,
                        verbose=False,
                        skip_sentiment=False,
                    )
                    logger.info(
                        "Startup news fetch complete: fetched=%d saved=%d",
                        stats.get("fetched", 0),
                        stats.get("saved", 0),
                    )
                if not session_obtained:
                    raise RuntimeError("Could not obtain DB session for startup news fetch")

                return  # Success — exit retry loop

            except Exception:
                if attempt < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** (attempt - 1))  # 15s, 30s, 60s
                    logger.warning(
                        "Startup news fetch failed (attempt %d/%d) — retrying in %ds",
                        attempt,
                        MAX_RETRIES,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.exception("Startup news fetch failed after %d attempts — giving up", MAX_RETRIES)
    finally:
        await _release_startup_lock("news_ingest")


async def _brsapi_startup_sync() -> None:
    """
    Startup sync: fetch ALL BrsApi endpoints in order.
    Respects rate limits automatically (the rate limiter enforces 10K/day, 500/5min).

    Retries up to 3 times with exponential backoff (30s, 60s, 120s) on failure.
    Guarded by a distributed lock (``startup:brsapi_sync``) so concurrent
    workers — or the API alongside the SchedulerApp — never run the full
    sync at the same time and race on the same tables.
    """
    if not await _with_startup_lock("brsapi_sync", "brsapi-sync"):
        return
    MAX_RETRIES = 3
    BASE_DELAY = 30  # seconds

    try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                from brsapi.client import get_client
                from brsapi.services.sync_service import BrsApiSyncService

                logger.info("=" * 60)
                logger.info(
                    "BrsApi STARTUP SYNC — attempt %d/%d — fetching ALL endpoints in order", attempt, MAX_RETRIES
                )
                logger.info("=" * 60)

                client = await get_client()
                session_obtained = False

                async for session in get_session():
                    session_obtained = True
                    service = BrsApiSyncService(client=client, session=session)

                    # sync_all runs every endpoint in sequence, respecting rate limits
                    reports = await service.sync_all(session)

                    # Log summary
                    ok = sum(1 for r in reports if r.success)
                    fail = sum(1 for r in reports if not r.success)
                    skipped = sum(1 for r in reports if r.skipped)
                    total_items = sum(r.items_count for r in reports)
                    total_ms = sum(r.duration_ms for r in reports)

                    logger.info("=" * 60)
                    logger.info("STARTUP SYNC COMPLETE: %d ok, %d failed, %d skipped", ok, fail, skipped)
                    logger.info("Total items synced: %d | Total time: %.1fs", total_items, total_ms / 1000)
                    logger.info("=" * 60)

                    for r in reports:
                        status = "OK" if r.success else ("SKIP" if r.skipped else "FAIL")
                        logger.info(
                            "  [%s] %s — %d items, %.0fms%s",
                            status,
                            r.endpoint,
                            r.items_count,
                            r.duration_ms,
                            f" — {r.error}" if r.error else "",
                        )

                    # Log rate limiter status
                    from brsapi.rate_limiter import get_rate_limiter

                    rl_status = get_rate_limiter().status()
                    g = rl_status["global"]
                    logger.info(
                        "Rate limits: daily %d/%d (%.0f%%) | 5min %d/%d (%.0f%%)",
                        g["daily_count"],
                        g["daily_limit"],
                        g["daily_used_pct"],
                        g["5min_count"],
                        g["5min_limit"],
                        g["5min_used_pct"],
                    )

                    break

                if not session_obtained:
                    raise RuntimeError("Could not obtain DB session for BrsApi startup sync")

                return  # Success — exit retry loop

            except Exception:
                if attempt < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** (attempt - 1))  # 30s, 60s, 120s
                    logger.warning(
                        "BrsApi startup sync failed (attempt %d/%d) — retrying in %ds",
                        attempt,
                        MAX_RETRIES,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.exception("BrsApi startup sync failed after %d attempts — giving up", MAX_RETRIES)
    finally:
        await _release_startup_lock("brsapi_sync")


# ── Lifespan ──


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    scheduler_app = None
    setup_logging()

    # Sentry first (optional, env-guarded) so startup failures are captured too.
    try:
        from core.observability_sentry import init_sentry

        init_sentry(settings)
    except Exception:
        logger.warning("Sentry init failed (optional)", exc_info=True)

    try:
        settings.validate_production()
    except Exception:
        # Never boot a production process with an invalid security
        # configuration. Development keeps the historical warning-only
        # behavior, but production must fail closed so a bad SECRET_KEY,
        # CORS policy, or insecure cookie cannot reach live traffic.
        if settings.is_production:
            logger.critical("Production configuration validation failed", exc_info=True)
            raise
        logger.warning("Production validation skipped (development mode)", exc_info=True)

    # Database: resilient init
    try:
        await init_database()
    except Exception:
        logger.exception("Database init failed, continuing without DB")

    # ML models: optional
    try:
        register_all_models()
    except Exception:
        logger.warning("ML model registration failed (optional)")

    # Cache: resilient init
    cache = get_cache()
    try:
        await cache.initialize()
    except Exception:
        logger.warning("Cache init failed, using null cache")

    # Hydrate orchestrator cron/alert state from Redis (multi-worker sync)
    await _load_cron_state_from_store()

    # ── Start BrsApi usage recorder (daily usage report for admin) ──
    try:
        from brsapi.usage_recorder import get_usage_recorder

        get_usage_recorder().start()
        logger.info("BrsApi usage recorder started — flushing daily usage every 60s")
    except Exception:
        logger.warning("BrsApi usage recorder failed to start")

    # ── Start accuracy outcome flusher (audit S2: no silent outcome loss) ──
    try:
        from services.accuracy_outcome_queue import get_accuracy_outcome_queue

        get_accuracy_outcome_queue().start()
        logger.info("Accuracy outcome queue flusher started — flushing every 30s")
    except Exception:
        logger.warning("Accuracy outcome flusher failed to start")

    # ── Register rate limit notification callback ──
    try:
        from brsapi.rate_limiter import get_rate_limiter

        rl = get_rate_limiter()
        rl.on_threshold(_rate_limit_notify)
        logger.info(
            "Rate limiter initialized: daily=%d, 5min=%d",
            rl._daily_limit,
            rl._five_min_limit,
        )
    except Exception:
        logger.warning("Rate limiter notification setup failed")

    # ── Start BrsApi scheduler (periodic sync jobs) ──
    try:
        from apps.scheduler.app import SchedulerApp

        scheduler_app = SchedulerApp()
        scheduler_app.start()
        job_count = len(scheduler_app.scheduler.get_jobs())
        logger.info("BrsApi scheduler started with %d periodic jobs", job_count)
    except Exception:
        logger.exception("BrsApi scheduler startup failed — periodic syncs disabled")

    # ── Initial full sync (ALL endpoints, ordered) ──
    _track_background_task(_brsapi_startup_sync(), "brsapi-startup-sync")

    # Auto-fetch news in background
    _track_background_task(_fetch_news_on_startup(), "news-startup-ingest")

    # Auto-seed Decision Engine architecture data in background
    _track_background_task(_decision_engine_startup_seed(), "decision-engine-seed")

    # ── Start RealtimeService (WebSocket broadcasting) ──
    try:
        from services.realtime_service import get_realtime_service

        rt_service = get_realtime_service()
        await rt_service.start()
    except Exception:
        logger.exception("RealtimeService startup failed — WebSocket broadcasting disabled")

    # ── Start the Armor precompute event subscriber ──
    # Cross-process Celery workers publish contract events to Redis
    # (armor:events); without this hook they would only be consumed once the
    # first dashboard WebSocket client connects.
    try:
        from api.ws_manager import get_armor_ws_manager

        await get_armor_ws_manager().start_subscriber()
        logger.info("Armor precompute event subscriber started (channel: armor:events)")
    except Exception:
        logger.warning("Armor precompute event subscriber failed to start", exc_info=True)

    # ── Hourly orchestrator cron (signal generation + outcome tracking + auto-retrain) ──
    _track_background_task(_orchestrator_hourly_cron(), "orchestrator-hourly-cron")
    logger.info("Orchestrator hourly cron started — generating signals every 3600s")

    # ── Pre-warm the multi-market signals cache so the first page load is
    #    instant instead of blocking on a ~60s pipeline rebuild ──
    try:
        from apps.api.endpoints.multi_market_signals import warm_signal_cache

        _track_background_task(warm_signal_cache(), "signal-cache-warmup")
        logger.info("Signal cache warm-up scheduled at startup")
    except Exception:
        logger.exception("Failed to schedule signal cache warm-up")

    # ── Fund sync cron (every 15 min during market hours, daily at 2 AM) ──
    _track_background_task(_fund_sync_cron(), "fund-sync-cron")
    logger.info("Fund sync cron started — updating fund data every 15 min")

    # ── Warm the ModelLoader LRU cache for active watchlist/screener symbols ──
    _track_background_task(_ml_model_preload(), "ml-model-preload")
    logger.info("ML model preload scheduled at startup — warming cache for active symbols")

    logger.info("Starting %s", settings.app_name)
    yield

    # Stop producers before closing their DB/Redis dependencies. This also
    # handles CancelledError explicitly through gather(return_exceptions=True).
    await _stop_background_tasks()
    with suppress(Exception):
        from api.ws_manager import get_armor_ws_manager

        await get_armor_ws_manager().shutdown()
    with suppress(Exception):
        if scheduler_app is not None:
            scheduler_app.scheduler.shutdown(wait=False)
    with suppress(Exception):
        from services.realtime_service import get_realtime_service

        rt_service = get_realtime_service()
        await rt_service.stop()
    with suppress(Exception):
        await cache.close()
    with suppress(Exception):
        from brsapi.client import close_client

        await close_client()
    with suppress(Exception):
        from brsapi.usage_recorder import get_usage_recorder

        await get_usage_recorder().stop()
    with suppress(Exception):
        from services.accuracy_outcome_queue import get_accuracy_outcome_queue

        await get_accuracy_outcome_queue().stop()
    with suppress(Exception):
        await close_database()
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(InputSanitizationMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    # RequestContextMiddleware LAST → OUTERMOST layer so every downstream
    # middleware/handler can read request.state.trace_id.
    app.add_middleware(RequestContextMiddleware)

    register_error_handlers(app)

    @app.get("/")
    async def root():
        return RedirectResponse(url="/docs")

    # ── Prometheus metrics ──
    @app.get(settings.metrics_path, include_in_schema=False)
    async def metrics():
        """Prometheus text exposition of in-process metrics."""
        return PlainTextResponse(
            get_prometheus_exporter().export_text(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    # ── Orchestrator cron status endpoint ──
    @app.get("/api/v1/orchestrator-cron-status")
    async def orchestrator_cron_status():
        """Get the status of the hourly orchestrator cron."""
        from schemas.common.responses import ApiResponse

        await _load_cron_state_from_store()
        data = dict(_cron_state)
        data["history"] = list(data["history"])
        data["alerts"] = dict(_alert_state)
        # Derived health status for frontend display
        in_crisis = _alert_state["was_in_failure_streak"] > 0.0 or _alert_state["was_accuracy_below_50"] > 0.0
        data["health"] = {
            "status": "in_crisis" if in_crisis else "healthy",
            "failure_streak_active": _alert_state["was_in_failure_streak"] > 0.0,
            "accuracy_below_50_active": _alert_state["was_accuracy_below_50"] > 0.0,
            "last_critical_alert_sent": max(_alert_state["consecutive_failures"], _alert_state["accuracy_drop"]),
        }
        return ApiResponse(success=True, data=data)

    @app.get("/api/v1/orchestrator-cron-history")
    async def orchestrator_cron_history():
        """Get the rotating history of the last 100 cron runs.

        Each entry: {run, timestamp, signals, accuracy, retrain_count, success, error?, source?}
        Useful for frontend timeline charts showing signal counts and accuracy trends.
        """
        from schemas.common.responses import ApiResponse

        await _load_cron_state_from_store()
        return ApiResponse(success=True, data=list(_cron_state["history"]))

    @app.post("/api/v1/orchestrator-cron/toggle")
    async def orchestrator_cron_toggle(
        _user: dict = Depends(require_roles("admin")) if require_roles else None,  # type: ignore
    ):
        """Enable or disable the hourly orchestrator cron."""
        # Use distributed lock to prevent lost updates when two admins toggle concurrently.
        locked = await _with_startup_lock("cron_toggle", "cron-toggle")
        try:
            await _load_cron_state_from_store()
            _cron_state["enabled"] = not _cron_state["enabled"]
            await _save_cron_state_to_store()
            from schemas.common.responses import ApiResponse

            return ApiResponse(success=True, data={"enabled": _cron_state["enabled"]})
        finally:
            if locked:
                await _release_startup_lock("cron_toggle")

    @app.post("/api/v1/orchestrator-cron/run-now")
    async def orchestrator_cron_run_now(
        _user: dict = Depends(require_roles("admin")) if require_roles else None,  # type: ignore
    ):
        """Trigger an immediate orchestrator run (does not wait for the hourly tick).

        Returns the full orchestrator report including signals, accuracy, and retrain status.
        """
        from datetime import UTC, datetime

        from schemas.common.responses import ApiResponse
        from services.quant_signal_orchestrator import QuantSignalOrchestrator

        await _load_cron_state_from_store()
        orchestrator = QuantSignalOrchestrator()
        report = await orchestrator.generate(
            market_filter="all",
            timeframe_filter="all",
            min_confidence=0.35,
            limit=100,
            use_ml=True,
            use_voting=True,
            use_confidence_calibration=True,
        )
        d = report.to_dict()

        # Update cron state too
        _cron_state["last_run"] = datetime.now(UTC).isoformat()
        _cron_state["last_signal_count"] = len(d.get("signals", []))
        _cron_state["last_accuracy"] = d.get("accuracy", {})
        _cron_state["last_retrain_count"] = len(d.get("retrain", []))
        _cron_state["last_error"] = None
        _cron_state["run_count"] += 1
        _cron_state["history"].append(
            {
                "run": _cron_state["run_count"],
                "timestamp": _cron_state["last_run"],
                "signals": len(d.get("signals", [])),
                "accuracy": d.get("accuracy", {}).get("overall", 0),
                "retrain_count": len(d.get("retrain", [])),
                "success": True,
                "source": "manual",
            }
        )
        await _save_cron_state_to_store()

        return ApiResponse(success=True, data=d)

    # ── Rate limit status endpoint ──
    @app.get("/api/v1/rate-limits")
    async def rate_limit_status():
        """Check BrsApi rate limit status (daily, 5min, per-endpoint)."""
        from brsapi.rate_limiter import get_rate_limiter
        from schemas.common.responses import ApiResponse

        return ApiResponse(success=True, data=get_rate_limiter().status())

    # ── Cache health / stats endpoint ──
    @app.get("/api/v1/cache-stats")
    async def cache_stats():
        """Expose screener cache health metrics for the admin dashboard.

        Returns hit rate, eviction count, size, and TTL for both caches:
          - score_cache: ScoringEngine results cache (ScreenerPipeline)
          - prebuilt_cache: quote+history prebuilt data cache (ScreenerService)
        """
        from schemas.common.responses import ApiResponse
        from services.screener_service import ScreenerPipeline, ScreenerService

        return ApiResponse(
            success=True,
            data={
                "score_cache": ScreenerPipeline._score_cache.stats,
                "prebuilt_cache": ScreenerService._prebuilt_cache.stats,
            },
        )

    router = Router()
    app.include_router(router.setup(), prefix=settings.api_prefix)

    return app


app = create_app()
