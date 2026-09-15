from __future__ import annotations

import asyncio
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import settings
from core.logging import get_logger
from jobs import definitions as job_definitions
from jobs.job_dispatcher import job_dispatcher
from jobs.registry import job_registry

logger = get_logger(__name__)


class SchedulerApp:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
        self._queue_enabled = settings.job_queue_enabled
        self._publisher: Any = None

    # ── Execution strategy ────────────────────────────────────────────
    # Queue mode (multi-replica): push the job to Redis — a worker executes it
    # exactly once (distributed lock).  Fallback (single process / no Redis):
    # dispatch in-process exactly like before — see docs/job-queue.md.

    def _get_publisher(self):
        if self._publisher is None:
            from jobs.queue_publisher import get_job_queue_publisher

            self._publisher = get_job_queue_publisher()
        return self._publisher

    async def _execute(self, job_name: str) -> None:
        if self._queue_enabled:
            published = await self._get_publisher().publish(job_name)
            if published is not None:
                logger.info("Scheduler queued job: %s", job_name)
                return
            logger.warning(
                "Scheduler could not enqueue %s — falling back to in-process dispatch",
                job_name,
            )
        logger.info("Scheduler running job in-process: %s", job_name)
        await job_dispatcher.dispatch(job_name)

    def add_job(self, job_name: str, trigger: str = "interval", **kwargs: Any) -> None:
        async def wrapper() -> None:
            await self._execute(job_name)

        self.scheduler.add_job(wrapper, trigger, **kwargs)
        logger.info(
            "Scheduled job %s with %s (mode=%s)",
            job_name,
            trigger,
            "queue" if self._queue_enabled else "in-process",
        )

    def start(self) -> None:
        # ── Register all job classes so dispatcher can find them ──
        job_registry.register_module(job_definitions)

        # ── BrsApi periodic sync jobs (registered via dedicated registry) ──
        from brsapi.jobs.registry import register_all_brsapi_jobs

        brsapi_registry = register_all_brsapi_jobs()
        if self._queue_enabled:
            # Queue mode: APScheduler only *triggers*; workers execute.
            brsapi_registry.run_handler = lambda name: self._get_publisher().publish(name)
        brsapi_registry.register_with_apscheduler(self.scheduler)

        # ── Legacy sync jobs (now proper BaseJob classes with DB sessions) ──
        self.add_job("SyncInstrumentsJob", trigger="interval", hours=24)
        self.add_job("SyncQuotesJob", trigger="interval", minutes=2)
        self.add_job("SyncSnapshotsToQuotesJob", trigger="interval", minutes=2)
        self.add_job("SyncCodalJob", trigger="interval", hours=6)
        self.add_job(
            "CodalAttachmentDownloadJob",
            trigger="interval",
            minutes=15,
            max_instances=1,
            replace_existing=True,
        )
        # NAV is published daily — sync each morning and again after market
        # close. sync_nav is idempotent per (symbol, date), so the second run
        # costs zero quota when the morning run already captured today's NAV
        # and otherwise acts as a same-day retry.
        self.add_job("SyncNavAllJob", trigger="cron", hour="9,18", minute=0, max_instances=1, replace_existing=True)
        self.add_job("NewsIngestionJob", trigger="interval", minutes=10)

        # ── Evaluate user price/volume/RSI alerts against live data ──
        # Runs every 2 minutes so alerts fire shortly after the condition holds.
        self.add_job("EvaluateAlertsJob", trigger="interval", minutes=2, max_instances=1, replace_existing=True)

        # ── Backfill historical data (daily, off-peak hours) ──
        self.add_job(
            "BackfillHistoricalDataJob",
            trigger="cron",
            hour=2,  # Run at 2 AM Tehran time
            minute=0,
            max_instances=1,  # Never run two backfills concurrently
            replace_existing=True,
        )

        # ── Sync fund snapshots into the `funds` table (from synced data) ──
        self.add_job(
            "FundsSyncJob",
            trigger="cron",
            hour=17,
            minute=30,
            max_instances=1,
            replace_existing=True,
        )

        # ── Paper trading: journal generated signals + settle simulated P&L ──
        self.add_job(
            "PaperTradingJob",
            trigger="cron",
            hour=21,  # After market close, off-peak
            minute=0,
            max_instances=1,
            replace_existing=True,
        )

        # ── Feature store: rebuild ml_engineered_features nightly ─────────
        # Runs at 23:30 — after the 21:00 symbol-detail refresh so the latest
        # details are available to the FeatureEngine. max_instances=1 avoids
        # concurrent runs across scheduler restarts.
        self.add_job(
            "FeatureStoreBuildJob",
            trigger="cron",
            hour=23,
            minute=30,
            max_instances=1,
            replace_existing=True,
        )

        # ── Screener daily scores snapshot (nightly) ─────────────────────
        # Runs 15min after the feature store so both nightly jobs don't
        # hammer the DB at the same instant.
        self.add_job(
            "ScreenerDailyScoresJob",
            trigger="cron",
            hour=23,
            minute=45,
            max_instances=1,
            replace_existing=True,
        )

        # ── BrsApi key-readiness probe (hourly) ─────────────────────────
        # 1 request/hour (24/day — negligible vs the 4,000/day cap). While
        # the key is blocked (BRSAPI_ENABLED=false, DB-only mode) this
        # watches for the server-side usage counter reset (HTTP 200 instead
        # of the 302 heavy-file redirect) and notifies so the operator can
        # flip the kill switch back on and run the backlog sync.
        self.add_job(
            "BrsApiReadyCheckJob",
            trigger="interval",
            hours=1,
            max_instances=1,
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("Scheduler started with %d BrsApi jobs", len(register_all_brsapi_jobs().enabled))

    async def run_forever(self) -> None:
        # Init Redis cache in the background so JobLocking uses the
        # distributed (Redis) lock in this process instead of the
        # single-process in-memory fallback. Non-blocking: until the
        # connection is ready, JobLocking degrades to in-memory locking.
        try:
            from core.cache import get_cache

            asyncio.create_task(get_cache().initialize())
        except Exception:
            logger.warning("Redis cache init failed; scheduler falls back to in-memory locks")
        self.start()
        while True:
            await asyncio.sleep(3600)
