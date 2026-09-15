from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from jobs.market_hours import is_tehran_codal_window, is_tehran_market_open

logger = get_logger(__name__)


_QUOTA_SAVING_NOTE = (
    " skipped outside Tehran market hours to preserve the free BrsApi daily quota"
    " (otherwise the TSETMC endpoints answer HTTP 402 by morning)"
)
_CODAL_WINDOW_NOTE = (
    " skipped outside the Tehran office-hours window to preserve the free"
    " BrsApi daily quota (otherwise Codal answers HTTP 402 by morning)"
)


class SyncInstrumentsJob(BaseJob):
    """Sync all TSETMC instruments/symbols via BrsApi.

    Delegates to BrsApiSyncService.sync_all_symbols() which fetches
    the full symbol list (prices, volumes, metadata) and stores them
    in the brsapi_symbol_snapshots table.
    """

    async def execute(self, context: JobContext) -> JobResult:
        if not is_tehran_market_open():
            logger.info("SyncInstrumentsJob%s", _QUOTA_SAVING_NOTE)
            return JobResult.success_result(
                job_name=self._name,
                data={"skipped": True, "message": "Outside Tehran market hours"},
            )
        from brsapi.client import get_client
        from brsapi.config import BrsApiEndpoints
        from brsapi.models import SymbolSnapshotModel
        from brsapi.parsers import TsetmcParser
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        report = None
        items = 0
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=BrsApiEndpoints.ALL_SYMBOLS,
                    parser=TsetmcParser.parse_all_symbols,
                    model_class=SymbolSnapshotModel,
                    params={"type": "1"},
                    session=session,
                )
                items = report.items_count
            # commit() fires after the async for loop completes
            if report and report.success:
                return JobResult.success_result(
                    job_name=self._name,
                    data={"synced": items, "endpoint": "ALL_SYMBOLS"},
                )
            return JobResult.failure(
                report.error if report else "Could not obtain DB session",
                job_name=self._name,
            )
        except Exception as e:
            logger.exception("SyncInstrumentsJob failed")
            return JobResult.failure(str(e), job_name=self._name)
        finally:
            pass


class SyncQuotesJob(BaseJob):
    """Sync all quotes (price/volume data) via BrsApi.

    Uses the same ALL_SYMBOLS endpoint as SyncInstrumentsJob since
    BrsApi returns price/volume/quotes in the same snapshot call.
    Also fetches indices for market-wide quote context.
    """

    async def execute(self, context: JobContext) -> JobResult:
        if not is_tehran_market_open():
            logger.info("SyncQuotesJob%s", _QUOTA_SAVING_NOTE)
            return JobResult.success_result(
                job_name=self._name,
                data={"skipped": True, "message": "Outside Tehran market hours"},
            )
        from brsapi.client import get_client
        from brsapi.config import BrsApiEndpoints
        from brsapi.models import IndexValueModel, SymbolSnapshotModel
        from brsapi.parsers import TsetmcParser
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        try:
            symbols_count = 0
            indices_count = 0
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                # Sync all symbols (includes price/volume).
                # NOTE: truncate_first MUST stay False — the brsapi_all_symbols
                # job writes to the SAME table every 2 minutes. Truncating here
                # would race with it (and with EvaluateAlertsJob reading it),
                # silently wiping snapshot data and causing alerts to skip.
                symbols_report = await service.sync(
                    endpoint=BrsApiEndpoints.ALL_SYMBOLS,
                    parser=TsetmcParser.parse_all_symbols,
                    model_class=SymbolSnapshotModel,
                    params={"type": "1"},
                    truncate_first=False,
                    session=session,
                )
                symbols_count = symbols_report.items_count
                # Also sync index values
                idx_report = await service.sync(
                    endpoint=BrsApiEndpoints.INDEX,
                    parser=TsetmcParser.parse_index,
                    model_class=IndexValueModel,
                    params={"type": "1"},
                    session=session,
                )
                indices_count = idx_report.items_count
            # commit() fires after the async for loop completes
            return JobResult.success_result(
                job_name=self._name,
                data={"symbols": symbols_count, "indices": indices_count},
            )
        except Exception as e:
            logger.exception("SyncQuotesJob failed")
            return JobResult.failure(str(e), job_name=self._name)
        finally:
            pass


class SyncCodalJob(BaseJob):
    """Sync Codal announcements via BrsApi.

    Delegates to BrsApiSyncService.sync_codal() which fetches
    recent announcements and stores them in brsapi_codal_announcements.
    """

    async def execute(self, context: JobContext) -> JobResult:
        if not is_tehran_codal_window():
            logger.info("SyncCodalJob%s", _CODAL_WINDOW_NOTE)
            return JobResult.success_result(
                job_name=self._name,
                data={"skipped": True, "message": "Outside Tehran office-hours window"},
            )
        from brsapi.client import get_client
        from brsapi.config import BrsApiEndpoints
        from brsapi.models import CodalAnnouncementModel
        from brsapi.parsers import CodalParser
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        report = None
        items = 0
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=BrsApiEndpoints.CODAL_ANNOUNCEMENT,
                    parser=CodalParser.parse_announcements_only,
                    model_class=CodalAnnouncementModel,
                    session=session,
                )
                items = report.items_count
            # commit() fires after the async for loop completes
            if report and report.success:
                return JobResult.success_result(
                    job_name=self._name,
                    data={"synced": items, "endpoint": "CODAL_ANNOUNCEMENT"},
                )
            return JobResult.failure(
                report.error if report else "Could not obtain DB session",
                job_name=self._name,
            )
        except Exception as e:
            logger.exception("SyncCodalJob failed")
            return JobResult.failure(str(e), job_name=self._name)
        finally:
            pass


# ── Legacy stub functions (kept for CLI/script backwards compatibility) ──


async def sync_instruments(source: str = "tsetmc") -> dict[str, Any]:
    """Deprecated stub — use SyncInstrumentsJob instead."""
    logger.info("sync_instruments is deprecated — use SyncInstrumentsJob (BaseJob class)")
    return {"status": "completed", "source": source, "count": 0}


async def sync_quotes(source: str = "tsetmc") -> dict[str, Any]:
    """Deprecated stub — use SyncQuotesJob instead."""
    logger.info("sync_quotes is deprecated — use SyncQuotesJob (BaseJob class)")
    return {"status": "completed", "source": source, "count": 0}


async def sync_codal(source: str = "codal") -> dict[str, Any]:
    """Deprecated stub — use SyncCodalJob instead."""
    logger.info("sync_codal is deprecated — use SyncCodalJob (BaseJob class)")
    return {"status": "completed", "source": source, "count": 0}


class SyncSnapshotsToQuotesJob(BaseJob):
    """Copy latest symbol snapshots from brsapi_symbol_snapshots to quotes table.

    This bridges the gap between the real-time BrsApi data pipeline and the
    legacy `quotes` table used by the frontend and backtesting engine.
    For each symbol with a snapshot, it extracts today's latest OHLCV + orderbook
    data and upserts it into the `quotes` table.
    """

    BATCH_SIZE = 500  # rows per batch commit

    async def execute(self, context: JobContext) -> JobResult:
        from sqlalchemy import text

        from core.database import async_session_factory

        if async_session_factory is None:
            return JobResult.failure("Database not available", job_name=self._name)

        async with async_session_factory() as session:
            # ── 1. Get the latest snapshot per symbol (today's data) ──
            #    The snapshots table is append-only with a fetched_at timestamp.
            #    NOTE: fetched_at is a TIMESTAMPTZ column — the cutoff MUST be a
            #    datetime/date object. asyncpg infers the parameter type from the
            #    column and raises `DataError: expected a datetime.date or
            #    datetime.datetime instance, got 'str'` when given a string.
            today = datetime.combine(datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)
            try:
                rows = await session.execute(
                    text("""
                    SELECT DISTINCT ON (s.symbol)
                        s.symbol,
                        s.ins_id,
                        s.price_close,
                        s.price_first,
                        s.price_max,
                        s.price_min,
                        s.price_last,
                        s.price_last_change,
                        s.price_last_change_pct,
                        s.price_yesterday,
                        s.trade_volume,
                        s.trade_value,
                        s.trade_count,
                        s.bid_price_1,
                        s.bid_volume_1,
                        s.ask_price_1,
                        s.ask_volume_1,
                        s.time,
                        s.fetched_at
                    FROM brsapi_symbol_snapshots s
                    WHERE s.fetched_at >= :today
                      AND s.symbol IS NOT NULL AND s.symbol != ''
                    ORDER BY s.symbol, s.fetched_at DESC
                """),
                    {"today": today},
                )
                snapshots = rows.fetchall()
            except Exception as e:
                logger.exception("Failed to query snapshots")
                return JobResult.failure(f"Query error: {e}", job_name=self._name)

            if not snapshots:
                logger.info("No today snapshots found to copy to quotes")
                return JobResult.success_result(
                    job_name=self._name,
                    data={"copied": 0, "skipped": 0, "message": "No today data"},
                )

            logger.info("Found %d snapshots to copy to quotes", len(snapshots))

            # ── 2. Upsert into quotes ──
            upsert_sql = text("""
                INSERT INTO quotes (
                    id, instrument_id, symbol,
                    price_close, price_open, price_high, price_low, price_last,
                    price_change, price_change_pct, price_yesterday,
                    price_first, price_max, price_min,
                    volume, value, trade_count,
                    bid_price, bid_volume, ask_price, ask_volume,
                    time, date, data_source
                ) VALUES (
                    :id, :instrument_id, :symbol,
                    :price_close, :price_open, :price_high, :price_low, :price_last,
                    :price_change, :price_change_pct, :price_yesterday,
                    :price_first, :price_max, :price_min,
                    :volume, :value, :trade_count,
                    :bid_price, :bid_volume, :ask_price, :ask_volume,
                    :time, :date, :data_source
                )
                ON CONFLICT (id) DO UPDATE SET
                    price_close = EXCLUDED.price_close,
                    price_last = EXCLUDED.price_last,
                    price_change = EXCLUDED.price_change,
                    price_change_pct = EXCLUDED.price_change_pct,
                    volume = EXCLUDED.volume,
                    value = EXCLUDED.value,
                    trade_count = EXCLUDED.trade_count,
                    time = EXCLUDED.time
            """)

            copied = 0
            skipped = 0
            batch = []

            for row in snapshots:
                # SQLAlchemy Row objects support dict-like access via _mapping
                row_dict = row._mapping
                symbol = row_dict["symbol"]
                fetched_at_raw = row_dict["fetched_at"]
                # fetched_at is a datetime object (TIMESTAMPTZ column)
                fetched_at = str(fetched_at_raw) if fetched_at_raw is not None else ""
                # Extract date from fetched_at (ISO format: "2026-07-09 09:24:15")
                if isinstance(fetched_at_raw, datetime):
                    date_str = fetched_at_raw.date().isoformat()
                else:
                    date_str = fetched_at[:10] if len(fetched_at) >= 10 else fetched_at
                record_id = f"brsapi_{symbol}_{date_str}"

                record = {
                    "id": record_id,
                    "instrument_id": row_dict["ins_id"] or "",
                    "symbol": symbol,
                    "price_close": row_dict["price_close"],
                    "price_open": row_dict["price_first"],
                    "price_high": row_dict["price_max"],
                    "price_low": row_dict["price_min"],
                    "price_last": row_dict["price_last"],
                    "price_change": row_dict["price_last_change"],
                    "price_change_pct": row_dict["price_last_change_pct"],
                    "price_yesterday": row_dict["price_yesterday"],
                    "price_first": row_dict["price_first"],
                    "price_max": row_dict["price_max"],
                    "price_min": row_dict["price_min"],
                    "volume": row_dict["trade_volume"],
                    "value": row_dict["trade_value"],
                    "trade_count": row_dict["trade_count"],
                    "bid_price": row_dict["bid_price_1"],
                    "bid_volume": row_dict["bid_volume_1"],
                    "ask_price": row_dict["ask_price_1"],
                    "ask_volume": row_dict["ask_volume_1"],
                    "time": row_dict["time"],
                    "date": date_str,
                    "data_source": "brsapi",
                }
                batch.append(record)

                if len(batch) >= self.BATCH_SIZE:
                    try:
                        await session.execute(upsert_sql, batch)
                        copied += len(batch)
                    except Exception as e:
                        logger.warning("Batch insert failed (%d rows): %s", len(batch), e)
                        skipped += len(batch)
                    batch = []

            # Final batch
            if batch:
                try:
                    await session.execute(upsert_sql, batch)
                    copied += len(batch)
                except Exception as e:
                    logger.warning("Final batch insert failed (%d rows): %s", len(batch), e)
                    skipped += len(batch)

            await session.commit()

        logger.info("Copy complete: %d copied, %d skipped", copied, skipped)
        return JobResult.success_result(
            job_name=self._name,
            data={"copied": copied, "skipped": skipped},
        )


class SyncNavAllJob(BaseJob):
    """Sync NAV for all ETF/fund symbols via BrsApi.

    Iterates through known fund symbols, fetches NAV per symbol from
    /Tsetmc/Nav.php, and stores results in brsapi_nav_records.  Rate limit
    is respected (1 req / 10s).
    """

    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        report = None
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync_nav_all(session)
            if report is None:
                return JobResult.failure("Could not obtain DB session", job_name=self._name)

            if report.items_count == 0 and not report.error:
                logger.warning("SyncNavAllJob: no fund symbols discovered and no NAV data synced")

            return JobResult.success_result(
                job_name=self._name,
                data={
                    "success": report.success,
                    "items_count": report.items_count,
                    "duration_ms": report.duration_ms,
                    "error": report.error,
                    "failed_symbols": report.failed_symbols,
                },
            )
        except Exception as e:
            logger.exception("SyncNavAllJob failed")
            return JobResult.failure(str(e), job_name=self._name)
        finally:
            pass


async def sync_news(source: str = "rss") -> dict[str, Any]:
    """Deprecated stub — news ingestion is now handled by NewsIngestionJob.

    Use NewsIngestionJob (scheduled by SchedulerApp) which properly uses a DB session.
    """
    from core.database import get_session
    from services.news_ingestion import NewsIngestionService

    logger.info("Running news sync via NewsIngestionService (with DB session)")
    stats: dict[str, Any] = {}
    session_obtained = False
    async for session in get_session():
        session_obtained = True
        service = NewsIngestionService(session=session)
        stats = await service.ingest(sources=[source] if source != "rss" else None, save=True, verbose=False)
        logger.info("News sync complete: fetched=%d saved=%d", stats.get("fetched", 0), stats.get("saved", 0))
    # commit() fires AFTER the async for loop completes naturally
    if not session_obtained:
        return {"status": "failed", "error": "Could not obtain DB session"}
    return {"status": "completed", **stats}
