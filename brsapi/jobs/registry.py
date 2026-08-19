"""
BrsApi job definitions for periodic data synchronisation.

Each job is an ``BrsApiSyncJob`` that wraps a sync operation with
logging, error handling, and the correct sync interval.

The registry makes it easy to bulk-register all jobs with APScheduler.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytz

from brsapi.client import BrsApiClient, get_client
from brsapi.config import BrsApiEndpoints, EndpointConfig
from brsapi.config import settings as brsapi_settings
from brsapi.models import GoldCurrencyProPriceModel
from brsapi.services.sync_service import BrsApiSyncService, SyncReport
from core.database import get_session
from core.logging import get_logger
from jobs.market_hours import is_tehran_codal_window, is_tehran_market_open

logger = get_logger(__name__)


# ──────────────────────────────────────────────
#  Sync Job Definition
# ──────────────────────────────────────────────


@dataclass
class BrsApiSyncJob:
    """
    Descriptor for a single BrsApi synchronisation job.

    Attributes:
        name: Human-readable job name.
        endpoint_config: The BrsApi endpoint to call.
        cron: Cron expression or interval seconds.
        category: Override rate-limiter category.
        params: Optional static URL params.
        enabled: Whether the job runs by default.
        description: What this job does.
    """
    name: str
    endpoint_config: EndpointConfig
    cron: str | int                     # "*/5 * * * *" or interval seconds
    category: str | None = None
    params: dict[str, str] | None = None
    enabled: bool = True
    description: str = ""
    # When True the job only runs inside Tehran trading hours — the free
    # BrsApi daily quota is reserved for when the market is actually open.
    market_hours_only: bool = False
    # When True (together with market_hours_only) the job follows the wider
    # Codal office-hours window (08:00–18:00) instead of trading hours,
    # because announcements are usually published after the session.
    codal_window: bool = False
    # Optional override so users can still force a sync out of hours
    # via the manage API (``run_job_now`` bypasses the gate).
    forced: bool = field(default=False, repr=False)


# ──────────────────────────────────────────────
#  Pre-defined Jobs
# ──────────────────────────────────────────────

# Default sync intervals as cron expressions
_EVERY_30_SEC = 30
_EVERY_1_MIN = 60
_EVERY_2_MIN = 120
_EVERY_5_MIN = 300
_EVERY_15_MIN = 900
_EVERY_1_HOUR = 3600
_EVERY_DAY_AT_9AM = "0 9 * * *"
_EVERY_DAY_AT_6PM = "0 18 * * *"
# After Tehran market close (12:30) — candlestick backfill window.
_EVERY_DAY_AT_1PM = "0 13 * * *"
# Shareholder backfill runs 30min later so the two quota-hungry full-market
# jobs don't hammer the API in the same instant.
_EVERY_DAY_AT_1_30PM = "30 13 * * *"
# History backfills follow at 30-min offsets: price at 14:00, real/legal at
# 14:30 — each 30min after the previous quota-hungry full-market job.
_EVERY_DAY_AT_2PM = "0 14 * * *"
_EVERY_DAY_AT_2_30PM = "30 14 * * *"
# Symbol-detail full-market refresh at night (21:00) — well after all the
# after-close backfills have finished so the shared API quota is fully
# available for the nightly symbol-detail refresh.
_EVERY_NIGHT_AT_9PM = "0 21 * * *"

# Tehran weekend: Thursday + Friday (Python weekday 3/4).
_TEHRAN_WEEKEND_DAYS = (3, 4)


def _is_tehran_weekend(now: datetime | None = None) -> bool:
    """True when ``now`` (Tehran wall-clock) is a Thursday or Friday.

    Used to skip the quota-hungry candlestick backfill on days the Tehran
    market is closed. Fails open (returns False) on tz errors so a broken
    timezone never blocks a backfill.
    """
    try:
        current = now or datetime.now(pytz.timezone(brsapi_settings.market_timezone))
        return current.weekday() in _TEHRAN_WEEKEND_DAYS
    except Exception:  # noqa: BLE001
        logger.warning("Tehran weekend check failed; allowing backfill", exc_info=True)
        return False


BRsAPI_SYNC_JOBS: list[BrsApiSyncJob] = [
    # ── TSETMC Realtime ──────────────────────────
    BrsApiSyncJob(
        name="brsapi_all_symbols",
        endpoint_config=BrsApiEndpoints.ALL_SYMBOLS,
        cron=_EVERY_2_MIN,
        description="Sync all TSETMC symbols (prices, volumes, orderbook)",
        market_hours_only=True,
    ),
    BrsApiSyncJob(
        name="brsapi_index",
        endpoint_config=BrsApiEndpoints.INDEX,
        cron=_EVERY_2_MIN,
        category="tsetmc",
        params={"type": "1"},
        description="Sync TSE main index",
        market_hours_only=True,
    ),
    BrsApiSyncJob(
        name="brsapi_index_farabours",
        endpoint_config=BrsApiEndpoints.INDEX,
        cron=_EVERY_2_MIN,
        category="tsetmc",
        params={"type": "2"},
        description="Sync Farabours index",
        market_hours_only=True,
    ),
    BrsApiSyncJob(
        name="brsapi_options",
        endpoint_config=BrsApiEndpoints.OPTION,
        cron=_EVERY_5_MIN,
        description="Sync TSETMC option contracts",
        market_hours_only=True,
    ),
    # ── NAV Realtime ────────────────────────────
    BrsApiSyncJob(
        name="brsapi_nav",
        endpoint_config=BrsApiEndpoints.NAV,
        cron=_EVERY_5_MIN,
        enabled=False,
        description="(DISABLED) NAV requires per-symbol l18 param. Called on-demand via sync_nav(symbol)",
    ),
    # ── TSETMC Historical / Per-Symbol ──────────
    BrsApiSyncJob(
        name="brsapi_history_price",
        endpoint_config=BrsApiEndpoints.HISTORY_PRICE,
        cron=_EVERY_1_HOUR,
        enabled=False,
        description="(DISABLED) History requires per-symbol l18 param. Called on-demand via sync_history_price(symbol)",
    ),
    BrsApiSyncJob(
        name="brsapi_history_real_legal",
        endpoint_config=BrsApiEndpoints.HISTORY_REALLEGAL,
        cron=_EVERY_1_HOUR,
        enabled=False,
        description="(DISABLED) History real/legal requires per-symbol l18 param. Called on-demand via sync_history_real_legal(symbol)",
    ),
    # ── IME ─────────────────────────────────────
    BrsApiSyncJob(
        name="brsapi_ime_futures",
        endpoint_config=BrsApiEndpoints.IME_FUTURES,
        cron=_EVERY_5_MIN,
        description="Sync IME futures contracts",
        market_hours_only=True,
    ),
    BrsApiSyncJob(
        name="brsapi_ime_options",
        endpoint_config=BrsApiEndpoints.IME_OPTION,
        cron=_EVERY_5_MIN,
        description="Sync IME option contracts",
        market_hours_only=True,
    ),
    BrsApiSyncJob(
        name="brsapi_ime_certificates",
        endpoint_config=BrsApiEndpoints.IME_CERTIFICATE,
        cron=_EVERY_5_MIN,
        description="Sync IME certificate/depository receipts",
        market_hours_only=True,
    ),
    BrsApiSyncJob(
        name="brsapi_ime_funds",
        endpoint_config=BrsApiEndpoints.IME_FUND,
        cron=_EVERY_5_MIN,
        description="Sync IME commodity funds",
        market_hours_only=True,
    ),
    # ── Global Markets ──────────────────────────
    BrsApiSyncJob(
        name="brsapi_commodities",
        endpoint_config=BrsApiEndpoints.COMMODITY,
        cron=_EVERY_5_MIN,  # Changed from 1min to 5min
        description="Sync global commodity prices",
    ),
    BrsApiSyncJob(
        name="brsapi_crypto",
        endpoint_config=BrsApiEndpoints.CRYPTOCURRENCY,
        cron=_EVERY_5_MIN,  # Changed from 1min to 5min
        description="Sync cryptocurrency prices",
    ),
    # ── Gold & Forex ────────────────────────────
    BrsApiSyncJob(
        name="brsapi_gold_currency",
        endpoint_config=BrsApiEndpoints.GOLD_CURRENCY,
        cron=_EVERY_5_MIN,
        description="Sync gold, currency & crypto via combined Gold_Currency.php endpoint",
    ),
    # ── Gold & Currency Pro ────────────────────────
    BrsApiSyncJob(
        name="brsapi_gold_currency_pro",
        endpoint_config=BrsApiEndpoints.GOLD_CURRENCY_PRO,
        cron=_EVERY_5_MIN,
        description="Sync gold, currency & crypto via Gold_Currency_Pro.php endpoint (Pro prices)",
    ),
    BrsApiSyncJob(
        name="brsapi_gold_currency_pro_history_24h",
        endpoint_config=BrsApiEndpoints.GOLD_CURRENCY_PRO,
        cron=_EVERY_1_HOUR,
        enabled=False,
        description="(DISABLED) 24h tick history for Pro symbols — enabled on-demand due to per-symbol API calls",
    ),
    BrsApiSyncJob(
        name="brsapi_gold_currency_pro_daily_history",
        endpoint_config=BrsApiEndpoints.GOLD_CURRENCY_PRO,
        cron=_EVERY_DAY_AT_6PM,
        enabled=False,
        description="(DISABLED) Daily OHLC history for Pro symbols — enabled on-demand due to per-symbol API calls",
    ),
    BrsApiSyncJob(
        name="brsapi_gold_coin",
        endpoint_config=BrsApiEndpoints.GOLD_COIN,
        cron=_EVERY_1_MIN,
        enabled=False,
        description="(DISABLED) Old gold/coin endpoint returns 404. Gold data is synced via sync_gold_currency() startup task",
    ),
    BrsApiSyncJob(
        name="brsapi_currency",
        endpoint_config=BrsApiEndpoints.CURRENCY,
        cron=_EVERY_1_MIN,
        enabled=False,
        description="(DISABLED) Old currency endpoint returns 404. Currency data synced via sync_gold_currency() startup task",
    ),
    # ── Codal ───────────────────────────────────
    BrsApiSyncJob(
        name="brsapi_codal",
        endpoint_config=BrsApiEndpoints.CODAL_ANNOUNCEMENT,
        cron=_EVERY_15_MIN,
        description="Sync Codal announcements",
        market_hours_only=True,
        codal_window=True,
    ),
    # ── Read-side enabled endpoints (data already synced by other jobs) ──
    # TRANSACTION is fetched on-demand via TradeService live fallback when
    # the local table is empty.  The endpoint requires per-symbol ``l18``
    # which makes it unsuitable for a global cron job.
    # ── Daily ───────────────────────────────────
    BrsApiSyncJob(
        name="brsapi_ime_physical",
        endpoint_config=BrsApiEndpoints.IME_PHYSICAL,
        cron=_EVERY_DAY_AT_6PM,
        description="Sync IME physical trades (daily after market close)",
    ),
    # ── Candlestick full-market backfill (daily after close) ──────────
    # Runs AFTER the Tehran market closes (13:00). Fetches the fresh
    # AllSymbols list, then for every symbol syncs all three candlestick
    # types: adjusted (3), unadjusted (2) and realtime intraday (1).
    # The API allows 2 req/10s on Candlestick, so symbols are processed in
    # daily chunks (``max_symbols``) and the run resumes with the symbols
    # that still lack candlestick data on subsequent days.
    BrsApiSyncJob(
        name="brsapi_candlesticks_all",
        endpoint_config=BrsApiEndpoints.CANDLESTICK,
        cron=_EVERY_DAY_AT_1PM,
        description="Daily 13:00 — AllSymbols + adjusted/unadjusted/realtime candlesticks for all symbols (chunked)",
    ),
    # ── Shareholder full-market backfill (daily after close) ──────────
    # Runs at 13:30 — 30 minutes AFTER the candlestick job so both
    # full-market backfills don't start at the same instant. Refreshes
    # AllSymbols and syncs the latest shareholder composition for every
    # symbol, chunked per day like the candlestick job.
    BrsApiSyncJob(
        name="brsapi_shareholders_all",
        endpoint_config=BrsApiEndpoints.SHAREHOLDER,
        cron=_EVERY_DAY_AT_1_30PM,
        description="Daily 13:30 — AllSymbols + latest shareholders for all symbols (chunked)",
    ),
    # ── History full-market backfills (daily after close) ──────────
    # Daily historical prices (14:00) and real/legal breakdown (14:30) for
    # every symbol — one request per symbol, chunked per day exactly like the
    # shareholder backfill, and 30min apart from each other and from the
    # shareholder job so the shared API quota is not hammered at once.
    BrsApiSyncJob(
        name="brsapi_history_price_all",
        endpoint_config=BrsApiEndpoints.HISTORY_PRICE,
        cron=_EVERY_DAY_AT_2PM,
        description="Daily 14:00 — AllSymbols + daily historical prices for all symbols (chunked)",
    ),
    BrsApiSyncJob(
        name="brsapi_history_real_legal_all",
        endpoint_config=BrsApiEndpoints.HISTORY_REALLEGAL,
        cron=_EVERY_DAY_AT_2_30PM,
        description="Daily 14:30 — AllSymbols + real/legal history for all symbols (chunked)",
    ),
    # ── Symbol-detail full-market refresh (nightly) ──────────
    # Runs every night at 21:00 — after all the after-close backfills have
    # finished so the shared API quota is fully available. Refreshes
    # AllSymbols and syncs the enriched Symbol.php detail for every symbol
    # (prices, order book, real/legal counts, assembly info, …), chunked per
    # day like the shareholder/history backfills. Feeds the /symbol-details
    # frontend page.
    BrsApiSyncJob(
        name="brsapi_symbol_details_all",
        endpoint_config=BrsApiEndpoints.SYMBOL_DETAIL,
        cron=_EVERY_NIGHT_AT_9PM,
        description="Every night 21:00 — AllSymbols + enriched symbol details for all symbols (chunked)",
    ),
]


# ──────────────────────────────────────────────
#  Job Registry
# ──────────────────────────────────────────────


class BrsApiJobRegistry:
    """
    Manages all BrsApi sync jobs and provides hooks for
    APScheduler/Celery Beat registration.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, BrsApiSyncJob] = {}
        self._client: BrsApiClient | None = None
        self._scheduler: Any = None
        # Optional runner override: when set, APScheduler-triggered jobs call
        # this instead of ``run_job`` directly. Used by the queue-based
        # architecture (scheduler pushes to Redis; workers execute). When
        # None (default) jobs run in-process — single-worker dev mode.
        self._run_handler: Any | None = None

    @property
    def run_handler(self) -> Any | None:
        """Async callable(job_name) used to run/queue jobs."""
        return self._run_handler

    @run_handler.setter
    def run_handler(self, handler: Any | None) -> None:
        """Set an async runner (e.g. ``lambda name: publisher.publish(name)``)."""
        self._run_handler = handler

    def register(self, job: BrsApiSyncJob) -> None:
        self._jobs[job.name] = job

    def register_many(self, jobs: list[BrsApiSyncJob]) -> None:
        for job in jobs:
            self.register(job)

    def get(self, name: str) -> BrsApiSyncJob | None:
        return self._jobs.get(name)

    @property
    def all(self) -> list[BrsApiSyncJob]:
        return list(self._jobs.values())

    @property
    def enabled(self) -> list[BrsApiSyncJob]:
        return [j for j in self._jobs.values() if j.enabled]

    # ── Scheduler management (for API toggling) ──

    @property
    def scheduler(self) -> Any:
        """Return the APScheduler instance, if set."""
        return self._scheduler

    @scheduler.setter
    def scheduler(self, scheduler: Any) -> None:
        self._scheduler = scheduler

    def list_all_jobs(self) -> list[dict[str, Any]]:
        """
        Return a serialisable list of all BrsApi sync jobs with their status.

        Each entry contains: name, enabled, cron, description, endpoint,
        category and the market-hours-only gate flag.
        """
        result = []
        for job in self._jobs.values():
            result.append({
                "name": job.name,
                "enabled": job.enabled,
                "cron": str(job.cron),
                "description": job.description,
                "endpoint": job.endpoint_config.path,
                "category": job.category or job.endpoint_config.category.value,
                "market_hours_only": job.market_hours_only,
            })
        return result

    def toggle_job(self, job_name: str) -> dict[str, Any]:
        """
        Toggle a job's enabled/disabled status at runtime.

        If the scheduler is running, the job is added or removed accordingly.

        Returns a dict with the job name, new enabled status, and a message.
        """
        job = self._jobs.get(job_name)
        if job is None:
            return {"name": job_name, "enabled": False, "message": f"Unknown job: {job_name}"}

        job.enabled = not job.enabled

        # Update APScheduler at runtime if running
        if self._scheduler is not None:
            if job.enabled:
                self._add_job_to_scheduler(job)
                logger.info("Added job '%s' to running scheduler (now enabled)", job_name)
            else:
                try:
                    self._scheduler.remove_job(job.name)
                    logger.info("Removed job '%s' from running scheduler (now disabled)", job_name)
                except Exception:
                    logger.warning("Job '%s' was not in running scheduler", job_name)

        return {
            "name": job_name,
            "enabled": job.enabled,
            "message": f"Job '{job_name}' is now {'enabled' if job.enabled else 'disabled'}",
        }

    async def run_job_now(self, job_name: str, force: bool = True) -> dict[str, Any]:
        """
        Trigger an immediate run of a job.

        Manual runs (e.g. from the manage API / web UI) bypass the
        ``market_hours_only`` gate by default so an admin can always
        force a sync; pass ``force=False`` to respect the gate.

        Returns a dict with job name, success status, and items count.
        """
        try:
            job = self._jobs.get(job_name)
            report = await self.run_job(job_name, force=force)
            if report is None:
                if job is not None and job.market_hours_only and not force:
                    return {
                        "name": job_name,
                        "success": False,
                        "skipped": True,
                        "message": f"Job '{job_name}' skipped: outside Tehran market hours",
                    }
                return {"name": job_name, "success": False, "message": f"Unknown or failed job: {job_name}"}
            return {
                "name": job_name,
                "success": report.success,
                "items_count": report.items_count,
                "duration_ms": report.duration_ms,
                "message": f"Job '{job_name}' completed: {report.items_count} items in {report.duration_ms:.0f}ms",
            }
        except Exception as exc:
            logger.exception("Failed to run job '%s'", job_name)
            return {"name": job_name, "success": False, "message": str(exc)}

    def _add_job_to_scheduler(self, job: BrsApiSyncJob) -> None:
        """Add a single job to the APScheduler."""
        if self._scheduler is None:
            return

        import pytz
        from apscheduler.triggers.cron import CronTrigger

        tz = pytz.timezone(brsapi_settings.market_timezone)

        async def _run(job_name: str = job.name) -> None:
            if self._run_handler is not None:
                # Queue mode: push the job, let a worker execute it.
                await self._run_handler(job_name)
            else:
                await self.run_job(job_name)

        if isinstance(job.cron, int):
            self._scheduler.add_job(
                _run,
                trigger="interval",
                seconds=job.cron,
                id=job.name,
                name=job.description,
                replace_existing=True,
                timezone=tz,
            )
        else:
            trigger = CronTrigger.from_crontab(job.cron, timezone=tz)
            self._scheduler.add_job(
                _run,
                trigger=trigger,
                id=job.name,
                name=job.description,
                replace_existing=True,
            )

    # ── APScheduler registration ────────────────

    def register_with_apscheduler(self, scheduler: Any) -> None:
        """
        Register all enabled jobs with an APScheduler instance.

        Also stores a reference to the scheduler for dynamic toggle operations.

        Args:
            scheduler: An APScheduler ``AsyncIOScheduler`` instance.
        """
        self._scheduler = scheduler

        for job in self.enabled:
            self._add_job_to_scheduler(job)
            logger.info("Registered APScheduler job: %s (cron=%s)", job.name, job.cron)

    # ── Helpers ───────────────────────────────

    async def _get_pro_symbols(self, session: Any, max_symbols: int = 50) -> list[str]:
        """
        Return distinct symbols for history sync jobs.

        Two input modes are supported:
        - an async SQLAlchemy session  → runs ``SELECT DISTINCT symbol``
          against ``GoldCurrencyProPriceModel`` with a ``LIMIT``;
        - a plain sequence of symbols (already loaded / test doubles)
          → filtered and sliced directly without touching the DB.

        Returns up to ``max_symbols`` symbols.
        """
        if isinstance(session, (list, tuple, set)):
            symbols = [s for s in session if s]
            return symbols[:max_symbols]

        from sqlalchemy import distinct, select

        stmt = select(distinct(GoldCurrencyProPriceModel.symbol)).limit(max_symbols)
        result = await session.execute(stmt)
        symbols = [row[0] for row in result if row[0]]
        logger.info("Found %d Pro symbols for history sync", len(symbols))
        return symbols

    # ── Run a single job ────────────────────────

    async def run_job(self, job_name: str, *, force: bool = False) -> SyncReport | None:
        """
        Execute a named sync job.

        Spins up its own DB session and client, runs the sync,
        then cleans up.

        Jobs flagged ``market_hours_only`` are skipped outside Tehran
        trading hours unless ``force=True`` (manual/on-demand runs).
        """
        job = self._jobs.get(job_name)
        if job is None:
            logger.warning("Unknown BrsApi job: %s", job_name)
            return None

        # ── Market-hours gate ─────────────────────────────────────
        # The free BrsApi tier has a limited daily quota. Running the
        # TSETMC/IME jobs around the clock burns it at night (market
        # closed) so by morning the API answers HTTP 402 and data stops
        # updating. Skip those jobs outside trading hours unless forced.
        if job.market_hours_only and not force:
            # Codal jobs use the wider office-hours window (announcements are
            # published after the session); everything else uses market hours.
            gate_open = is_tehran_codal_window() if job.codal_window else is_tehran_market_open()
            if not gate_open:
                logger.info(
                    "BrsApi job '%s' skipped: outside Tehran %s window (market_hours_only)",
                    job_name,
                    "Codal office-hours" if job.codal_window else "market hours",
                )
                return None

        logger.info("Running BrsApi job: %s", job_name)

        # Lazy client init
        if self._client is None:
            self._client = await get_client()

        async for session in get_session():
            service = BrsApiSyncService(client=self._client)

            # ── Special handler: sync_gold_currency is a composite job ──
            if job_name == "brsapi_gold_currency_pro":
                reports = await service.sync_gold_currency_pro(session)
                for r in reports:
                    logger.info(
                        "Gold_Currency_Pro/%s: %s (%d items in %.0fms)",
                        r.endpoint,
                        "OK" if r.success else "FAIL",
                        r.items_count,
                        r.duration_ms,
                    )
                return reports[0] if reports else None

            if job_name == "brsapi_gold_currency":
                reports = await service.sync_gold_currency(session)
                for r in reports:
                    logger.info(
                        "Gold_Currency/%s: %s (%d items in %.0fms)",
                        r.endpoint,
                        "OK" if r.success else "FAIL",
                        r.items_count,
                        r.duration_ms,
                    )
                # Return the first report as summary
                return reports[0] if reports else None

            # ── Special handler: Gold_Currency_Pro 24h history ──
            if job_name == "brsapi_gold_currency_pro_history_24h":
                symbols = await self._get_pro_symbols(session, max_symbols=20)
                if not symbols:
                    logger.warning("No Pro symbols found — run brsapi_gold_currency_pro first")
                    return None

                all_reports: list[SyncReport] = []
                for sym in symbols:
                    report = await service.sync_gold_currency_pro_history_24h(session, symbol=sym)
                    all_reports.append(report)
                    logger.info(
                        "Gold_Currency_Pro_24h/%s: %s (%d items in %.0fms)",
                        sym,
                        "OK" if report.success else "FAIL",
                        report.items_count,
                        report.duration_ms,
                    )
                    await asyncio.sleep(0.5)  # Polite delay between symbols
                await session.commit()
                return all_reports[0] if all_reports else None

            # ── Special handler: Gold_Currency_Pro daily history ──
            if job_name == "brsapi_gold_currency_pro_daily_history":
                symbols = await self._get_pro_symbols(session, max_symbols=20)
                if not symbols:
                    logger.warning("No Pro symbols found — run brsapi_gold_currency_pro first")
                    return None

                all_reports = []
                for sym in symbols:
                    report = await service.sync_gold_currency_pro_daily_history(session, symbol=sym)
                    all_reports.append(report)
                    logger.info(
                        "Gold_Currency_Pro_Daily/%s: %s (%d items in %.0fms)",
                        sym,
                        "OK" if report.success else "FAIL",
                        report.items_count,
                        report.duration_ms,
                    )
                    await asyncio.sleep(0.5)
                await session.commit()
                return all_reports[0] if all_reports else None

            # ── Special handler: candlestick full-market backfill ──
            if job_name == "brsapi_candlesticks_all":
                return await self._run_candlesticks_all(session, service)

            # ── Special handler: shareholder full-market backfill ──
            if job_name == "brsapi_shareholders_all":
                return await self._run_shareholders_all(session, service)

            # ── Special handler: history full-market backfills ──
            if job_name == "brsapi_history_price_all":
                return await self._run_history_price_all(session, service)
            if job_name == "brsapi_history_real_legal_all":
                return await self._run_history_real_legal_all(session, service)

            # ── Special handler: symbol-detail full-market refresh ──
            if job_name == "brsapi_symbol_details_all":
                return await self._run_symbol_details_all(session, service)

            # ── Standard single-endpoint sync ──
            report = await service.sync(
                endpoint=job.endpoint_config,
                parser=self._get_parser(job.endpoint_config),
                model_class=self._get_model(job.endpoint_config),
                params=job.params,
                category_override=job.category,
                session=session,
            )
            logger.info(
                "Job %s: %s (%d items in %.0fms)",
                job_name,
                "OK" if report.success else "FAIL",
                report.items_count,
                report.duration_ms,
            )
            return report

        return None

    # ── Candlestick full-market backfill (daily after close) ──

    async def _run_candlesticks_all(
        self,
        session: Any,
        service: BrsApiSyncService,
        *,
        max_symbols: int | None = None,
        sleep_s: float | None = None,
        allow_weekend: bool = False,
        progress: dict[str, Any] | None = None,
    ) -> SyncReport | None:
        """Daily-after-close candlestick backfill for the whole market.

        Steps:
          1. Refresh the AllSymbols list (brsapi_symbol_snapshots) so the
             symbol set matches the live market. If the fresh list is
             EMPTY the market is very likely closed (holiday) — the whole
             backfill is skipped instead of re-syncing from stale symbols.
          2. Load all distinct symbols from the snapshots table.
          3. Sort so symbols WITHOUT any candlestick rows are processed
             first (fresh backfill); previously-synced symbols are caught
             up later.
          4. For each symbol (up to ``max_symbols`` per run) sync all three
             candlestick types: adjusted (3), unadjusted (2), realtime (1).

        The global rate limiter (1000 req/5min, 10000/day) is the real gate;
        ``brsapi_settings.candle_req_delay`` (default 0.2s) is only a small
        politeness spacing and the daily chunk is bounded by
        (``brsapi_settings.candle_daily_max_symbols``, default 1000).
        Re-running the job on later days automatically resumes with the
        still-missing symbols.

        Overridable parameters:
        - ``max_symbols``: cap the number of symbols processed in this run
          (0 or None = settings default; pass a value to override).
        - ``sleep_s``: seconds between API requests (default from settings).
        - ``allow_weekend``: skip the Tehran weekend guard (manual runs).
        - ``progress``: optional mutable dict updated with live progress
          (status, processed, ok, fail, items, current_symbol, message).
          Setting ``progress["cancel_requested"] = True`` stops the run
          after the current symbol.

        Tehran weekend (Thu/Fri) is skipped to conserve the free API quota
        — no new trades exist then, and type=1 returns ``no_data`` anyway.
        """
        from sqlalchemy import select

        from brsapi.models import CandlestickModel, SymbolSnapshotModel

        # Tehran weekend guard — skip on Thursday/Friday (Python weekday 3/4)
        # unless the caller explicitly allows weekend runs.
        if not allow_weekend and _is_tehran_weekend():
            logger.info("Candlestick daily: Tehran weekend — skipped to save quota")
            return SyncReport(
                endpoint=BrsApiEndpoints.CANDLESTICK.path,
                success=True,
                items_count=0,
                skipped=True,
            )

        if max_symbols is None:
            max_symbols = brsapi_settings.candle_daily_max_symbols
        if sleep_s is None:
            sleep_s = brsapi_settings.candle_req_delay

        # 1. Refresh the live symbol list
        symbols_report = await service.sync_all_symbols(session)
        logger.info(
            "Candlestick daily: AllSymbols refresh %s (%d items)",
            "OK" if symbols_report.success else "FAIL",
            symbols_report.items_count,
        )
        await session.commit()

        # If the fresh AllSymbols fetch succeeded but returned ZERO symbols
        # the market is almost certainly closed/holiday — there are no new
        # candles to fetch, so skip instead of re-syncing from the stale
        # symbol list still held in the snapshots table.
        if symbols_report.success and symbols_report.items_count == 0:
            logger.info(
                "Candlestick daily: AllSymbols returned 0 symbols — "
                "market closed/holiday, skipping candle backfill",
            )
            return SyncReport(
                endpoint=BrsApiEndpoints.CANDLESTICK.path,
                success=True,
                items_count=0,
                skipped=True,
            )

        # 2. All distinct symbols from the snapshots table
        stmt = select(SymbolSnapshotModel.symbol).distinct()
        result = await session.execute(stmt)
        symbols = [row[0] for row in result if row[0]]
        if not symbols:
            logger.warning("Candlestick daily: no symbols found — aborting")
            return None

        # 3. Symbols already holding candlestick rows
        have = await session.execute(
            select(CandlestickModel.symbol).distinct()
        )
        have_set = {row[0] for row in have if row[0]}
        # Missing symbols first (fresh backfill), then already-synced ones.
        missing = [s for s in symbols if s not in have_set]
        done = [s for s in symbols if s in have_set]
        ordered = missing + done
        # max_symbols <= 0 means "no limit" (whole market).
        if max_symbols <= 0:
            max_symbols = len(ordered)
        chunk = ordered[:max_symbols]
        logger.info(
            "Candlestick daily: %d symbols total (%d missing) — processing %d today",
            len(ordered),
            len(missing),
            len(chunk),
        )

        if progress is not None:
            progress.update({
                "status": "running",
                "total_symbols": len(chunk),
                "processed": 0,
                "ok": 0,
                "fail": 0,
                "items": 0,
                "current_symbol": None,
                "message": f"آماده‌سازی: {len(chunk)} نماد برای پردازش",
            })

        # 4. Sync all three types for each symbol in the chunk
        total_items = 0
        ok = fail = 0
        failed: list[str] = []
        cancelled = False
        start = time.monotonic()
        for i, sym in enumerate(chunk):
            # Honour a user-requested cancellation between symbols.
            if progress is not None and progress.get("cancel_requested"):
                cancelled = True
                logger.info("Candlestick daily: cancel requested — stopping at %s", sym)
                break
            is_last = i == len(chunk) - 1
            for candle_type in ("3", "2", "1"):
                try:
                    report = await service.sync_candlesticks(
                        session, sym, candle_type=candle_type
                    )
                    if report.success:
                        ok += 1
                        total_items += report.items_count
                    else:
                        fail += 1
                        failed.append(f"{sym}/type{candle_type}")
                        logger.warning(
                            "Candlestick daily %s type=%s: FAIL %s",
                            sym, candle_type, report.error,
                        )
                except Exception as exc:  # noqa: BLE001
                    fail += 1
                    failed.append(f"{sym}/type{candle_type}")
                    logger.exception(
                        "Candlestick daily %s type=%s: EXC %s",
                        sym, candle_type, exc,
                    )
                # Rate-limit spacing — skip the sleep after the very last
                # request of the run.
                if sleep_s > 0 and not (is_last and candle_type == "1"):
                    await asyncio.sleep(sleep_s)
            if progress is not None:
                progress.update({
                    "processed": i + 1,
                    "ok": ok,
                    "fail": fail,
                    "items": total_items,
                    "current_symbol": sym,
                    "message": f"{i + 1}/{len(chunk)} — {sym} (✅ {ok} | ❌ {fail})",
                })
            if (i + 1) % 25 == 0:
                logger.info(
                    "Candlestick daily progress: %d/%d symbols (%d ok, %d fail)",
                    i + 1, len(chunk), ok, fail,
                )

        await session.commit()
        duration_ms = (time.monotonic() - start) * 1000

        if cancelled:
            logger.info(
                "Candlestick daily cancelled: %d items in %.1fmin",
                total_items, duration_ms / 60000,
            )
            if progress is not None:
                progress.update({
                    "status": "cancelled",
                    "message": "بکفیل توسط کاربر متوقف شد",
                })
            return SyncReport(
                endpoint=BrsApiEndpoints.CANDLESTICK.path,
                success=True,
                items_count=total_items,
                duration_ms=duration_ms,
                skipped=True,
                error="Cancelled by user",
                failed_symbols=failed,
            )

        logger.info(
            "Candlestick daily done: %d symbols, %d items, %d ok / %d fail in %.1fmin",
            len(chunk),
            total_items,
            ok,
            fail,
            duration_ms / 60000,
        )
        error: str | None = None
        if fail:
            shown = failed[:10]
            suffix = f" and {len(failed) - 10} more" if len(failed) > 10 else ""
            error = f"{fail} requests failed: {', '.join(shown)}{suffix}"
        if progress is not None:
            progress.update({
                "status": "done",
                "processed": len(chunk),
                "ok": ok,
                "fail": fail,
                "items": total_items,
                "current_symbol": None,
                "message": f"کامل شد: {total_items} آیتم، {ok} موفق / {fail} خطا",
                "error": error,
            })
        return SyncReport(
            endpoint=BrsApiEndpoints.CANDLESTICK.path,
            success=fail == 0,
            items_count=total_items,
            duration_ms=duration_ms,
            error=error,
            failed_symbols=failed,
        )

    # ── Shareholder full-market backfill (daily after close) ──

    async def _run_shareholders_all(
        self,
        session: Any,
        service: BrsApiSyncService,
        *,
        max_symbols: int | None = None,
        sleep_s: float | None = None,
        allow_weekend: bool = False,
        progress: dict[str, Any] | None = None,
    ) -> SyncReport | None:
        """Daily-after-close shareholder backfill for the whole market.

        Mirrors ``_run_candlesticks_all``:
          1. Refresh the AllSymbols list. If the fresh list is EMPTY the
             market is very likely closed (holiday) — the whole backfill is
             skipped instead of re-syncing from stale symbols.
          2. Load all distinct symbols from the snapshots table.
          3. Sort so symbols WITHOUT any shareholder records are processed
             first (fresh backfill); already-synced symbols are caught up
             later.
          4. For each symbol (up to ``max_symbols`` per run) sync the latest
             shareholder composition.

        The Shareholder endpoint allows 2 req/10s (12 req/min), so every
        request is followed by a ``sleep``
        (``brsapi_settings.shareholder_req_delay``, default 5s) and the daily
        chunk is bounded (``brsapi_settings.shareholder_daily_max_symbols``,
        default 1000). Re-running the job on later days automatically resumes
        with the still-missing symbols.

        Overridable parameters:
        - ``max_symbols``: cap the number of symbols processed in this run
          (0 or None = settings default; pass a value to override).
        - ``sleep_s``: seconds between API requests (default from settings).
        - ``allow_weekend``: skip the Tehran weekend guard (manual runs).
        - ``progress``: optional mutable dict updated with live progress
          (status, processed, ok, fail, items, current_symbol, message).
          Setting ``progress["cancel_requested"] = True`` stops the run
          after the current symbol.
        """
        from sqlalchemy import select

        from brsapi.models import ShareholderRecordModel, SymbolSnapshotModel

        # Tehran weekend guard — skip on Thursday/Friday (Python weekday 3/4)
        # unless the caller explicitly allows weekend runs.
        if not allow_weekend and _is_tehran_weekend():
            logger.info("Shareholder daily: Tehran weekend — skipped to save quota")
            if progress is not None:
                progress["message"] = "بکفیل اجرا نشد — روز آخر هفته تهران"
            return SyncReport(
                endpoint=BrsApiEndpoints.SHAREHOLDER.path,
                success=True,
                items_count=0,
                skipped=True,
            )

        if max_symbols is None:
            max_symbols = brsapi_settings.shareholder_daily_max_symbols
        if sleep_s is None:
            sleep_s = brsapi_settings.shareholder_req_delay

        # 1. Refresh the live symbol list
        symbols_report = await service.sync_all_symbols(session)
        logger.info(
            "Shareholder daily: AllSymbols refresh %s (%d items)",
            "OK" if symbols_report.success else "FAIL",
            symbols_report.items_count,
        )
        await session.commit()

        # If the fresh AllSymbols fetch succeeded but returned ZERO symbols
        # the market is almost certainly closed/holiday — skip instead of
        # re-syncing from the stale symbol list still held in snapshots.
        if symbols_report.success and symbols_report.items_count == 0:
            logger.info(
                "Shareholder daily: AllSymbols returned 0 symbols — "
                "market closed/holiday, skipping shareholder backfill",
            )
            if progress is not None:
                progress["message"] = "بکفیل اجرا نشد — بازار بسته/تعطیل است (AllSymbols خالی)"
            return SyncReport(
                endpoint=BrsApiEndpoints.SHAREHOLDER.path,
                success=True,
                items_count=0,
                skipped=True,
            )

        # 2. All distinct symbols from the snapshots table
        stmt = select(SymbolSnapshotModel.symbol).distinct()
        result = await session.execute(stmt)
        symbols = [row[0] for row in result if row[0]]
        if not symbols:
            logger.warning("Shareholder daily: no symbols found — aborting")
            return None

        # 3. Symbols already holding shareholder records
        have = await session.execute(
            select(ShareholderRecordModel.symbol).distinct()
        )
        have_set = {row[0] for row in have if row[0]}
        # Missing symbols first (fresh backfill), then already-synced ones.
        missing = [s for s in symbols if s not in have_set]
        done = [s for s in symbols if s in have_set]
        ordered = missing + done
        # max_symbols <= 0 means "no limit" (whole market).
        if max_symbols <= 0:
            max_symbols = len(ordered)
        chunk = ordered[:max_symbols]
        logger.info(
            "Shareholder daily: %d symbols total (%d missing) — processing %d today",
            len(ordered),
            len(missing),
            len(chunk),
        )

        if progress is not None:
            progress.update({
                "status": "running",
                "total_symbols": len(chunk),
                "processed": 0,
                "ok": 0,
                "fail": 0,
                "items": 0,
                "current_symbol": None,
                "message": f"آماده‌سازی: {len(chunk)} نماد برای پردازش",
            })

        # 4. Sync the latest shareholder composition for each symbol
        total_items = 0
        ok = fail = 0
        failed: list[str] = []
        cancelled = False
        start = time.monotonic()
        for i, sym in enumerate(chunk):
            # Honour a user-requested cancellation between symbols.
            if progress is not None and progress.get("cancel_requested"):
                cancelled = True
                logger.info("Shareholder daily: cancel requested — stopping at %s", sym)
                break
            is_last = i == len(chunk) - 1
            try:
                report = await service.sync_shareholders(session, sym)
                if report.success:
                    ok += 1
                    total_items += report.items_count
                else:
                    fail += 1
                    failed.append(sym)
                    logger.warning(
                        "Shareholder daily %s: FAIL %s", sym, report.error,
                    )
            except Exception as exc:  # noqa: BLE001
                fail += 1
                failed.append(sym)
                logger.exception(
                    "Shareholder daily %s: EXC %s", sym, exc,
                )
            # Rate-limit spacing — skip the sleep after the very last request.
            if sleep_s > 0 and not is_last:
                await asyncio.sleep(sleep_s)
            if progress is not None:
                progress.update({
                    "processed": i + 1,
                    "ok": ok,
                    "fail": fail,
                    "items": total_items,
                    "current_symbol": sym,
                    "message": f"{i + 1}/{len(chunk)} — {sym} (✅ {ok} | ❌ {fail})",
                })
            if (i + 1) % 25 == 0:
                logger.info(
                    "Shareholder daily progress: %d/%d symbols (%d ok, %d fail)",
                    i + 1, len(chunk), ok, fail,
                )

        await session.commit()
        duration_ms = (time.monotonic() - start) * 1000

        if cancelled:
            logger.info(
                "Shareholder daily cancelled: %d items in %.1fmin",
                total_items, duration_ms / 60000,
            )
            if progress is not None:
                progress.update({
                    "status": "cancelled",
                    "message": "بکفیل توسط کاربر متوقف شد",
                })
            return SyncReport(
                endpoint=BrsApiEndpoints.SHAREHOLDER.path,
                success=True,
                items_count=total_items,
                duration_ms=duration_ms,
                skipped=True,
                error="Cancelled by user",
                failed_symbols=failed,
            )

        logger.info(
            "Shareholder daily done: %d symbols, %d items, %d ok / %d fail in %.1fmin",
            len(chunk),
            total_items,
            ok,
            fail,
            duration_ms / 60000,
        )
        error: str | None = None
        if fail:
            shown = failed[:10]
            suffix = f" and {len(failed) - 10} more" if len(failed) > 10 else ""
            error = f"{fail} requests failed: {', '.join(shown)}{suffix}"
        if progress is not None:
            progress.update({
                "status": "done",
                "processed": len(chunk),
                "ok": ok,
                "fail": fail,
                "items": total_items,
                "current_symbol": None,
                "message": f"کامل شد: {total_items} آیتم، {ok} موفق / {fail} خطا",
                "error": error,
            })
        return SyncReport(
            endpoint=BrsApiEndpoints.SHAREHOLDER.path,
            success=fail == 0,
            items_count=total_items,
            duration_ms=duration_ms,
            error=error,
            failed_symbols=failed,
        )

    # ── History full-market backfills (daily after close) ──

    async def _run_history_price_all(
        self,
        session: Any,
        service: BrsApiSyncService,
        **kwargs: Any,
    ) -> SyncReport | None:
        """Daily-after-close backfill of daily historical prices."""
        return await self._run_history_backfill(
            session, service, kind="price", **kwargs,
        )

    async def _run_history_real_legal_all(
        self,
        session: Any,
        service: BrsApiSyncService,
        **kwargs: Any,
    ) -> SyncReport | None:
        """Daily-after-close backfill of the real/legal buy-sell breakdown."""
        return await self._run_history_backfill(
            session, service, kind="real_legal", **kwargs,
        )

    async def _run_history_backfill(
        self,
        session: Any,
        service: BrsApiSyncService,
        *,
        kind: str = "price",  # "price" | "real_legal"
        max_symbols: int | None = None,
        sleep_s: float | None = None,
        allow_weekend: bool = False,
        progress: dict[str, Any] | None = None,
    ) -> SyncReport | None:
        """Daily-after-close history backfill for the whole market.

        Mirrors ``_run_shareholders_all`` (one request per symbol):
          1. Refresh the AllSymbols list — an EMPTY fresh list means the
             market is closed/holiday and the backfill is skipped.
          2. Load all distinct symbols from the snapshots table.
          3. Sort so symbols WITHOUT any history rows are processed first.
          4. For each symbol (up to ``max_symbols`` per run) sync the history
             via ``sync_history_price`` / ``sync_history_real_legal``.

        One request per symbol at ``history_*_req_delay`` spacing (default
        5s), chunked per day (``history_*_daily_max_symbols``, default 500).
        Re-running on later days resumes with the still-missing symbols.

        Overridable parameters mirror the shareholder backfill:
        ``max_symbols``, ``sleep_s``, ``allow_weekend`` and ``progress``
        (setting ``progress["cancel_requested"] = True`` stops the run).
        """
        from sqlalchemy import select

        from brsapi.models import (
            HistoricalDailyModel,
            HistoricalRealLegalModel,
            SymbolSnapshotModel,
        )

        if kind == "real_legal":
            endpoint = BrsApiEndpoints.HISTORY_REALLEGAL
            model_cls = HistoricalRealLegalModel
            sync_fn = service.sync_history_real_legal
            default_max = brsapi_settings.history_real_legal_daily_max_symbols
            default_delay = brsapi_settings.history_real_legal_req_delay
            label = "HistoryRealLegal"
        else:
            endpoint = BrsApiEndpoints.HISTORY_PRICE
            model_cls = HistoricalDailyModel
            sync_fn = service.sync_history_price
            default_max = brsapi_settings.history_price_daily_max_symbols
            default_delay = brsapi_settings.history_price_req_delay
            label = "HistoryPrice"

        # Tehran weekend guard — skip on Thursday/Friday unless the caller
        # explicitly allows weekend runs.
        if not allow_weekend and _is_tehran_weekend():
            logger.info("%s daily: Tehran weekend — skipped to save quota", label)
            if progress is not None:
                progress["message"] = "بکفیل اجرا نشد — روز آخر هفته تهران"
            return SyncReport(
                endpoint=endpoint.path,
                success=True,
                items_count=0,
                skipped=True,
            )

        if max_symbols is None:
            max_symbols = default_max
        if sleep_s is None:
            sleep_s = default_delay

        # 1. Refresh the live symbol list
        symbols_report = await service.sync_all_symbols(session)
        logger.info(
            "%s daily: AllSymbols refresh %s (%d items)",
            label,
            "OK" if symbols_report.success else "FAIL",
            symbols_report.items_count,
        )
        await session.commit()

        # If the fresh AllSymbols fetch succeeded but returned ZERO symbols
        # the market is almost certainly closed/holiday — skip instead of
        # re-syncing from the stale symbol list still held in snapshots.
        if symbols_report.success and symbols_report.items_count == 0:
            logger.info(
                "%s daily: AllSymbols returned 0 symbols — "
                "market closed/holiday, skipping backfill",
                label,
            )
            if progress is not None:
                progress["message"] = "بکفیل اجرا نشد — بازار بسته/تعطیل است (AllSymbols خالی)"
            return SyncReport(
                endpoint=endpoint.path,
                success=True,
                items_count=0,
                skipped=True,
            )

        # 2. All distinct symbols from the snapshots table
        stmt = select(SymbolSnapshotModel.symbol).distinct()
        result = await session.execute(stmt)
        symbols = [row[0] for row in result if row[0]]
        if not symbols:
            logger.warning("%s daily: no symbols found — aborting", label)
            return None

        # 3. Symbols already holding history rows
        have = await session.execute(
            select(model_cls.symbol).distinct()
        )
        have_set = {row[0] for row in have if row[0]}
        # Missing symbols first (fresh backfill), then already-synced ones.
        missing = [s for s in symbols if s not in have_set]
        done = [s for s in symbols if s in have_set]
        ordered = missing + done
        # max_symbols <= 0 means "no limit" (whole market).
        if max_symbols <= 0:
            max_symbols = len(ordered)
        chunk = ordered[:max_symbols]
        logger.info(
            "%s daily: %d symbols total (%d missing) — processing %d today",
            label,
            len(ordered),
            len(missing),
            len(chunk),
        )

        if progress is not None:
            progress.update({
                "status": "running",
                "total_symbols": len(chunk),
                "processed": 0,
                "ok": 0,
                "fail": 0,
                "items": 0,
                "current_symbol": None,
                "message": f"آماده‌سازی: {len(chunk)} نماد برای پردازش",
            })

        # 4. Sync history for each symbol in the chunk
        total_items = 0
        ok = fail = 0
        failed: list[str] = []
        cancelled = False
        start = time.monotonic()
        for i, sym in enumerate(chunk):
            # Honour a user-requested cancellation between symbols.
            if progress is not None and progress.get("cancel_requested"):
                cancelled = True
                logger.info("%s daily: cancel requested — stopping at %s", label, sym)
                break
            is_last = i == len(chunk) - 1
            try:
                report = await sync_fn(session, sym)
                if report.success:
                    ok += 1
                    total_items += report.items_count
                else:
                    fail += 1
                    failed.append(sym)
                    logger.warning("%s daily %s: FAIL %s", label, sym, report.error)
            except Exception as exc:  # noqa: BLE001
                fail += 1
                failed.append(sym)
                logger.exception("%s daily %s: EXC %s", label, sym, exc)
            # Rate-limit spacing — skip the sleep after the very last request.
            if sleep_s > 0 and not is_last:
                await asyncio.sleep(sleep_s)
            if progress is not None:
                progress.update({
                    "processed": i + 1,
                    "ok": ok,
                    "fail": fail,
                    "items": total_items,
                    "current_symbol": sym,
                    "message": f"{i + 1}/{len(chunk)} — {sym} (✅ {ok} | ❌ {fail})",
                })
            if (i + 1) % 25 == 0:
                logger.info(
                    "%s daily progress: %d/%d symbols (%d ok, %d fail)",
                    label, i + 1, len(chunk), ok, fail,
                )

        await session.commit()
        duration_ms = (time.monotonic() - start) * 1000

        if cancelled:
            logger.info(
                "%s daily cancelled: %d items in %.1fmin",
                label, total_items, duration_ms / 60000,
            )
            if progress is not None:
                progress.update({
                    "status": "cancelled",
                    "message": "بکفیل توسط کاربر متوقف شد",
                })
            return SyncReport(
                endpoint=endpoint.path,
                success=True,
                items_count=total_items,
                duration_ms=duration_ms,
                skipped=True,
                error="Cancelled by user",
                failed_symbols=failed,
            )

        logger.info(
            "%s daily done: %d symbols, %d items, %d ok / %d fail in %.1fmin",
            label, len(chunk), total_items, ok, fail, duration_ms / 60000,
        )
        error: str | None = None
        if fail:
            shown = failed[:10]
            suffix = f" and {len(failed) - 10} more" if len(failed) > 10 else ""
            error = f"{fail} requests failed: {', '.join(shown)}{suffix}"
        if progress is not None:
            progress.update({
                "status": "done",
                "processed": len(chunk),
                "ok": ok,
                "fail": fail,
                "items": total_items,
                "current_symbol": None,
                "message": f"کامل شد: {total_items} آیتم، {ok} موفق / {fail} خطا",
                "error": error,
            })
        return SyncReport(
            endpoint=endpoint.path,
            success=fail == 0,
            items_count=total_items,
            duration_ms=duration_ms,
            error=error,
            failed_symbols=failed,
        )

    # ── Symbol-detail full-market refresh (daily after close) ──

    async def _run_symbol_details_all(
        self,
        session: Any,
        service: BrsApiSyncService,
        *,
        max_symbols: int | None = None,
        sleep_s: float | None = None,
        allow_weekend: bool = False,
        progress: dict[str, Any] | None = None,
    ) -> SyncReport | None:
        """Daily-after-close refresh of enriched symbol details for the whole market.

        Mirrors the shareholder/history backfills:
          1. Refresh the AllSymbols list — an EMPTY fresh list means the
             market is closed/holiday and the refresh is skipped.
          2. Load all distinct symbols from the snapshots table.
          3. Sort so symbols WITHOUT any detail rows are processed first
             (fresh backfill); already-synced symbols are caught up later.
          4. For each symbol (up to ``max_symbols`` per run) sync the
             enriched detail via ``sync_symbol_detail``.

        One request per symbol at ``symbol_detail_req_delay`` spacing
        (default 4s — Symbol.php allows 3 req/10s), chunked per day
        (``symbol_detail_daily_max_symbols``, default 1000). Re-running on
        later days resumes with the still-missing symbols.

        Overridable parameters mirror the other backfills:
        ``max_symbols``, ``sleep_s``, ``allow_weekend`` and ``progress``
        (setting ``progress["cancel_requested"] = True`` stops the run).
        """
        from sqlalchemy import select

        from brsapi.models import SymbolDetailModel, SymbolSnapshotModel

        # Tehran weekend guard — skip on Thursday/Friday unless the caller
        # explicitly allows weekend runs.
        if not allow_weekend and _is_tehran_weekend():
            logger.info("SymbolDetail daily: Tehran weekend — skipped to save quota")
            if progress is not None:
                progress["message"] = "بکفیل اجرا نشد — روز آخر هفته تهران"
            return SyncReport(
                endpoint=BrsApiEndpoints.SYMBOL_DETAIL.path,
                success=True,
                items_count=0,
                skipped=True,
            )

        if max_symbols is None:
            max_symbols = brsapi_settings.symbol_detail_daily_max_symbols
        if sleep_s is None:
            sleep_s = brsapi_settings.symbol_detail_req_delay

        # 1. Refresh the live symbol list
        symbols_report = await service.sync_all_symbols(session)
        logger.info(
            "SymbolDetail daily: AllSymbols refresh %s (%d items)",
            "OK" if symbols_report.success else "FAIL",
            symbols_report.items_count,
        )
        await session.commit()

        # If the fresh AllSymbols fetch succeeded but returned ZERO symbols
        # the market is almost certainly closed/holiday — skip instead of
        # re-syncing from the stale symbol list still held in snapshots.
        if symbols_report.success and symbols_report.items_count == 0:
            logger.info(
                "SymbolDetail daily: AllSymbols returned 0 symbols — "
                "market closed/holiday, skipping symbol-detail refresh",
            )
            if progress is not None:
                progress["message"] = "بکفیل اجرا نشد — بازار بسته/تعطیل است (AllSymbols خالی)"
            return SyncReport(
                endpoint=BrsApiEndpoints.SYMBOL_DETAIL.path,
                success=True,
                items_count=0,
                skipped=True,
            )

        # 2. All distinct symbols from the snapshots table
        stmt = select(SymbolSnapshotModel.symbol).distinct()
        result = await session.execute(stmt)
        symbols = [row[0] for row in result if row[0]]
        if not symbols:
            logger.warning("SymbolDetail daily: no symbols found — aborting")
            return None

        # 3. Symbols already holding detail rows
        have = await session.execute(
            select(SymbolDetailModel.symbol).distinct()
        )
        have_set = {row[0] for row in have if row[0]}
        # Missing symbols first (fresh backfill), then already-synced ones.
        missing = [s for s in symbols if s not in have_set]
        done = [s for s in symbols if s in have_set]
        ordered = missing + done
        # max_symbols <= 0 means "no limit" (whole market).
        if max_symbols <= 0:
            max_symbols = len(ordered)
        chunk = ordered[:max_symbols]
        logger.info(
            "SymbolDetail daily: %d symbols total (%d missing) — processing %d today",
            len(ordered),
            len(missing),
            len(chunk),
        )

        if progress is not None:
            progress.update({
                "status": "running",
                "total_symbols": len(chunk),
                "processed": 0,
                "ok": 0,
                "fail": 0,
                "items": 0,
                "current_symbol": None,
                "message": f"آماده‌سازی: {len(chunk)} نماد برای پردازش",
            })

        # 4. Sync enriched detail for each symbol in the chunk
        total_items = 0
        ok = fail = 0
        failed: list[str] = []
        cancelled = False
        start = time.monotonic()
        for i, sym in enumerate(chunk):
            # Honour a user-requested cancellation between symbols.
            if progress is not None and progress.get("cancel_requested"):
                cancelled = True
                logger.info("SymbolDetail daily: cancel requested — stopping at %s", sym)
                break
            is_last = i == len(chunk) - 1
            try:
                report = await service.sync_symbol_detail(session, sym)
                if report.success:
                    ok += 1
                    total_items += report.items_count
                else:
                    fail += 1
                    failed.append(sym)
                    logger.warning("SymbolDetail daily %s: FAIL %s", sym, report.error)
            except Exception as exc:  # noqa: BLE001
                fail += 1
                failed.append(sym)
                logger.exception("SymbolDetail daily %s: EXC %s", sym, exc)
            # Rate-limit spacing — skip the sleep after the very last request.
            if sleep_s > 0 and not is_last:
                await asyncio.sleep(sleep_s)
            if progress is not None:
                progress.update({
                    "processed": i + 1,
                    "ok": ok,
                    "fail": fail,
                    "items": total_items,
                    "current_symbol": sym,
                    "message": f"{i + 1}/{len(chunk)} — {sym} (✅ {ok} | ❌ {fail})",
                })
            if (i + 1) % 25 == 0:
                logger.info(
                    "SymbolDetail daily progress: %d/%d symbols (%d ok, %d fail)",
                    i + 1, len(chunk), ok, fail,
                )

        await session.commit()
        duration_ms = (time.monotonic() - start) * 1000

        if cancelled:
            logger.info(
                "SymbolDetail daily cancelled: %d items in %.1fmin",
                total_items, duration_ms / 60000,
            )
            if progress is not None:
                progress.update({
                    "status": "cancelled",
                    "message": "بکفیل توسط کاربر متوقف شد",
                })
            return SyncReport(
                endpoint=BrsApiEndpoints.SYMBOL_DETAIL.path,
                success=True,
                items_count=total_items,
                duration_ms=duration_ms,
                skipped=True,
                error="Cancelled by user",
                failed_symbols=failed,
            )

        logger.info(
            "SymbolDetail daily done: %d symbols, %d items, %d ok / %d fail in %.1fmin",
            len(chunk), total_items, ok, fail, duration_ms / 60000,
        )
        error: str | None = None
        if fail:
            shown = failed[:10]
            suffix = f" and {len(failed) - 10} more" if len(failed) > 10 else ""
            error = f"{fail} requests failed: {', '.join(shown)}{suffix}"
        if progress is not None:
            progress.update({
                "status": "done",
                "processed": len(chunk),
                "ok": ok,
                "fail": fail,
                "items": total_items,
                "current_symbol": None,
                "message": f"کامل شد: {total_items} آیتم، {ok} موفق / {fail} خطا",
                "error": error,
            })
        return SyncReport(
            endpoint=BrsApiEndpoints.SYMBOL_DETAIL.path,
            success=fail == 0,
            items_count=total_items,
            duration_ms=duration_ms,
            error=error,
            failed_symbols=failed,
        )

    def _get_parser(self, ep: EndpointConfig) -> Any:
        """Return the appropriate parser function for an endpoint."""
        from brsapi.parsers import (
            CodalParser,
            CommodityParser,
            CryptoParser,
            CurrencyParser,
            GoldCoinParser,
            GoldCurrencyProParser,
            ImeParser,
            TsetmcParser,
        )

        mapping = {
            BrsApiEndpoints.ALL_SYMBOLS.path: TsetmcParser.parse_all_symbols,
            BrsApiEndpoints.SYMBOL_DETAIL.path: TsetmcParser.parse_symbol_detail,
            BrsApiEndpoints.INDEX.path: TsetmcParser.parse_index,
            BrsApiEndpoints.NAV.path: TsetmcParser.parse_nav,
            BrsApiEndpoints.OPTION.path: TsetmcParser.parse_options,
            BrsApiEndpoints.TRANSACTION.path: TsetmcParser.parse_transactions,
            BrsApiEndpoints.HISTORY_PRICE.path: TsetmcParser.parse_history_price,
            BrsApiEndpoints.HISTORY_REALLEGAL.path: TsetmcParser.parse_history_real_legal,
            BrsApiEndpoints.CANDLESTICK.path: TsetmcParser.parse_candlesticks,
            BrsApiEndpoints.SHAREHOLDER.path: TsetmcParser.parse_shareholders,
            BrsApiEndpoints.IME_FUTURES.path: ImeParser.parse_futures,
            BrsApiEndpoints.IME_OPTION.path: ImeParser.parse_options,
            BrsApiEndpoints.IME_CERTIFICATE.path: ImeParser.parse_certificates,
            BrsApiEndpoints.IME_FUND.path: ImeParser.parse_funds,
            BrsApiEndpoints.IME_PHYSICAL.path: ImeParser.parse_physical_trades,
            BrsApiEndpoints.COMMODITY.path: CommodityParser.parse,
            BrsApiEndpoints.CRYPTOCURRENCY.path: CryptoParser.parse,
            BrsApiEndpoints.GOLD_COIN.path: GoldCoinParser.parse,
            BrsApiEndpoints.GOLD_COIN_HISTORY.path: GoldCoinParser.parse_history,
            BrsApiEndpoints.CURRENCY.path: CurrencyParser.parse,
            BrsApiEndpoints.CURRENCY_HISTORY.path: CurrencyParser.parse,
            BrsApiEndpoints.GOLD_CURRENCY_PRO.path: GoldCurrencyProParser.parse_gold,
            BrsApiEndpoints.CODAL_ANNOUNCEMENT.path: CodalParser.parse_announcements_only,
        }
        return mapping.get(ep.path, TsetmcParser.parse_all_symbols)

    def _get_model(self, ep: EndpointConfig) -> Any:
        """Return the appropriate SQLAlchemy model class for an endpoint."""
        from brsapi.models import (
            CandlestickModel,
            CodalAnnouncementModel,
            CommodityPriceModel,
            CryptoPriceModel,
            CurrencyPriceModel,
            GoldCoinHistoryModel,
            GoldCoinPriceModel,
            HistoricalDailyModel,
            HistoricalRealLegalModel,
            ImeCertificateModel,
            ImeFundModel,
            ImeFutureModel,
            ImeOptionModel,
            ImePhysicalTradeModel,
            IndexValueModel,
            IntradayTradeModel,
            NavRecordModel,
            OptionSnapshotModel,
            ShareholderRecordModel,
            SymbolDetailModel,
            SymbolSnapshotModel,
        )

        mapping = {
            BrsApiEndpoints.ALL_SYMBOLS.path: SymbolSnapshotModel,
            BrsApiEndpoints.SYMBOL_DETAIL.path: SymbolDetailModel,
            BrsApiEndpoints.INDEX.path: IndexValueModel,
            BrsApiEndpoints.NAV.path: NavRecordModel,
            BrsApiEndpoints.OPTION.path: OptionSnapshotModel,
            BrsApiEndpoints.TRANSACTION.path: IntradayTradeModel,
            BrsApiEndpoints.HISTORY_PRICE.path: HistoricalDailyModel,
            BrsApiEndpoints.HISTORY_REALLEGAL.path: HistoricalRealLegalModel,
            BrsApiEndpoints.CANDLESTICK.path: CandlestickModel,
            BrsApiEndpoints.SHAREHOLDER.path: ShareholderRecordModel,
            BrsApiEndpoints.IME_FUTURES.path: ImeFutureModel,
            BrsApiEndpoints.IME_OPTION.path: ImeOptionModel,
            BrsApiEndpoints.IME_CERTIFICATE.path: ImeCertificateModel,
            BrsApiEndpoints.IME_FUND.path: ImeFundModel,
            BrsApiEndpoints.IME_PHYSICAL.path: ImePhysicalTradeModel,
            BrsApiEndpoints.COMMODITY.path: CommodityPriceModel,
            BrsApiEndpoints.CRYPTOCURRENCY.path: CryptoPriceModel,
            BrsApiEndpoints.GOLD_COIN.path: GoldCoinPriceModel,
            BrsApiEndpoints.GOLD_COIN_HISTORY.path: GoldCoinHistoryModel,
            BrsApiEndpoints.CURRENCY.path: CurrencyPriceModel,
            BrsApiEndpoints.CURRENCY_HISTORY.path: CurrencyPriceModel,
            BrsApiEndpoints.GOLD_CURRENCY_PRO.path: GoldCurrencyProPriceModel,
            BrsApiEndpoints.CODAL_ANNOUNCEMENT.path: CodalAnnouncementModel,
        }
        return mapping.get(ep.path, SymbolSnapshotModel)


# Global instance
_registry: BrsApiJobRegistry | None = None


def get_brsapi_job_registry() -> BrsApiJobRegistry:
    global _registry
    if _registry is None:
        _registry = BrsApiJobRegistry()
        _registry.register_many(BRsAPI_SYNC_JOBS)
    return _registry


def register_all_brsapi_jobs() -> BrsApiJobRegistry:
    """Convenience: return the fully-populated job registry."""
    return get_brsapi_job_registry()
