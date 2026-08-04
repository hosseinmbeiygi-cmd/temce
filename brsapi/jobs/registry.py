"""
BrsApi job definitions for periodic data synchronisation.

Each job is an ``BrsApiSyncJob`` that wraps a sync operation with
logging, error handling, and the correct sync interval.

The registry makes it easy to bulk-register all jobs with APScheduler.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

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

    # ── Parser / model lookup ───────────────────

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
