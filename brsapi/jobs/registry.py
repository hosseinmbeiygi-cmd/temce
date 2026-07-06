"""
BrsApi job definitions for periodic data synchronisation.

Each job is an ``BrsApiSyncJob`` that wraps a sync operation with
logging, error handling, and the correct sync interval.

The registry makes it easy to bulk-register all jobs with APScheduler.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from logging import getLogger
from typing import Any

from brsapi.client import BrsApiClient, get_client
from brsapi.config import BrsApiEndpoints, EndpointConfig, settings as brsapi_settings
from brsapi.services.sync_service import BrsApiSyncService, SyncReport
from core.database import get_session
from core.logging import get_logger

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


# ──────────────────────────────────────────────
#  Pre-defined Jobs
# ──────────────────────────────────────────────

# Default sync intervals as cron expressions
_EVERY_30_SEC = 30
_EVERY_1_MIN = 60
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
        cron=_EVERY_1_MIN,
        description="Sync all TSETMC symbols (prices, volumes, orderbook)",
    ),
    BrsApiSyncJob(
        name="brsapi_index",
        endpoint_config=BrsApiEndpoints.INDEX,
        cron=_EVERY_1_MIN,
        category="tsetmc",
        params={"type": "1"},
        description="Sync TSE main index",
    ),
    BrsApiSyncJob(
        name="brsapi_index_farabours",
        endpoint_config=BrsApiEndpoints.INDEX,
        cron=_EVERY_1_MIN,
        category="tsetmc",
        params={"type": "2"},
        description="Sync Farabours index",
    ),
    BrsApiSyncJob(
        name="brsapi_index_selected",
        endpoint_config=BrsApiEndpoints.INDEX,
        cron=_EVERY_5_MIN,
        category="tsetmc",
        params={"type": "3"},
        description="Sync selected indices",
    ),
    BrsApiSyncJob(
        name="brsapi_options",
        endpoint_config=BrsApiEndpoints.OPTION,
        cron=_EVERY_5_MIN,
        description="Sync TSETMC option contracts",
    ),
    # ── NAV Realtime ────────────────────────────
    BrsApiSyncJob(
        name="brsapi_nav",
        endpoint_config=BrsApiEndpoints.NAV,
        cron=_EVERY_5_MIN,
        description="Sync ETF NAV data (requires l18 param per symbol)",
    ),
    # ── TSETMC Historical / Per-Symbol ──────────
    BrsApiSyncJob(
        name="brsapi_history_price",
        endpoint_config=BrsApiEndpoints.HISTORY_PRICE,
        cron=_EVERY_1_HOUR,
        description="Sync daily historical prices (requires l18 per symbol)",
    ),
    BrsApiSyncJob(
        name="brsapi_history_real_legal",
        endpoint_config=BrsApiEndpoints.HISTORY_REALLEGAL,
        cron=_EVERY_1_HOUR,
        description="Sync daily real/legal data (requires l18 per symbol)",
    ),
    # ── IME ─────────────────────────────────────
    BrsApiSyncJob(
        name="brsapi_ime_futures",
        endpoint_config=BrsApiEndpoints.IME_FUTURES,
        cron=_EVERY_5_MIN,
        description="Sync IME futures contracts",
    ),
    BrsApiSyncJob(
        name="brsapi_ime_options",
        endpoint_config=BrsApiEndpoints.IME_OPTION,
        cron=_EVERY_5_MIN,
        description="Sync IME option contracts",
    ),
    BrsApiSyncJob(
        name="brsapi_ime_certificates",
        endpoint_config=BrsApiEndpoints.IME_CERTIFICATE,
        cron=_EVERY_5_MIN,
        description="Sync IME certificate/depository receipts",
    ),
    BrsApiSyncJob(
        name="brsapi_ime_funds",
        endpoint_config=BrsApiEndpoints.IME_FUND,
        cron=_EVERY_5_MIN,
        description="Sync IME commodity funds",
    ),
    # ── Global Markets ──────────────────────────
    BrsApiSyncJob(
        name="brsapi_commodities",
        endpoint_config=BrsApiEndpoints.COMMODITY,
        cron=_EVERY_1_MIN,
        description="Sync global commodity prices",
    ),
    BrsApiSyncJob(
        name="brsapi_crypto",
        endpoint_config=BrsApiEndpoints.CRYPTOCURRENCY,
        cron=_EVERY_1_MIN,
        description="Sync cryptocurrency prices",
    ),
    # ── Gold & Forex ────────────────────────────
    BrsApiSyncJob(
        name="brsapi_gold_coin",
        endpoint_config=BrsApiEndpoints.GOLD_COIN,
        cron=_EVERY_1_MIN,
        description="Sync gold & coin prices",
    ),
    BrsApiSyncJob(
        name="brsapi_gold_24h",
        endpoint_config=BrsApiEndpoints.GOLD_24H,
        cron=_EVERY_5_MIN,
        description="Sync 24-hour gold price changes",
    ),
    BrsApiSyncJob(
        name="brsapi_currency",
        endpoint_config=BrsApiEndpoints.CURRENCY,
        cron=_EVERY_1_MIN,
        description="Sync currency/forex prices",
    ),
    BrsApiSyncJob(
        name="brsapi_currency_24h",
        endpoint_config=BrsApiEndpoints.CURRENCY_24H,
        cron=_EVERY_5_MIN,
        description="Sync 24-hour currency changes",
    ),
    # ── Codal ───────────────────────────────────
    BrsApiSyncJob(
        name="brsapi_codal",
        endpoint_config=BrsApiEndpoints.CODAL_ANNOUNCEMENT,
        cron=_EVERY_15_MIN,
        description="Sync Codal announcements",
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

    # ── APScheduler registration ────────────────

    def register_with_apscheduler(self, scheduler: Any) -> None:
        """
        Register all enabled jobs with an APScheduler instance.

        Args:
            scheduler: An APScheduler ``AsyncIOScheduler`` instance.
        """
        import pytz

        tz = pytz.timezone(brsapi_settings.market_timezone)

        for job in self.enabled:
            async def _run(job_name: str = job.name) -> None:
                """APScheduler job wrapper."""
                await self.run_job(job_name)

            if isinstance(job.cron, int):
                # Interval-based trigger (seconds)
                scheduler.add_job(
                    _run,
                    trigger="interval",
                    seconds=job.cron,
                    id=job.name,
                    name=job.description,
                    replace_existing=True,
                    timezone=tz,
                )
            else:
                # Cron expression
                scheduler.add_job(
                    _run,
                    trigger="cron",
                    cron=job.cron,
                    id=job.name,
                    name=job.description,
                    replace_existing=True,
                    timezone=tz,
                )

            logger.info("Registered APScheduler job: %s (cron=%s)", job.name, job.cron)

    # ── Run a single job ────────────────────────

    async def run_job(self, job_name: str) -> SyncReport | None:
        """
        Execute a named sync job.

        Spins up its own DB session and client, runs the sync,
        then cleans up.
        """
        job = self._jobs.get(job_name)
        if job is None:
            logger.warning("Unknown BrsApi job: %s", job_name)
            return None

        logger.info("Running BrsApi job: %s", job_name)

        # Lazy client init
        if self._client is None:
            self._client = await get_client()

        async for session in get_session():
            service = BrsApiSyncService(client=self._client)
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
                "✓" if report.success else "✗",
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
            Gold24hParser,
            GoldCoinParser,
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
            BrsApiEndpoints.GOLD_24H.path: Gold24hParser.parse,
            BrsApiEndpoints.CURRENCY.path: CurrencyParser.parse,
            BrsApiEndpoints.CURRENCY_24H.path: CurrencyParser.parse_24h,
            BrsApiEndpoints.CURRENCY_HISTORY.path: CurrencyParser.parse,
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
            Currency24hModel,
            CurrencyPriceModel,
            Gold24hModel,
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
            BrsApiEndpoints.GOLD_24H.path: Gold24hModel,
            BrsApiEndpoints.CURRENCY.path: CurrencyPriceModel,
            BrsApiEndpoints.CURRENCY_24H.path: Currency24hModel,
            BrsApiEndpoints.CURRENCY_HISTORY.path: CurrencyPriceModel,
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
