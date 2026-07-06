from __future__ import annotations

from typing import Any

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)


class SyncInstrumentsJob(BaseJob):
    """Sync all TSETMC instruments/symbols via BrsApi.

    Delegates to BrsApiSyncService.sync_all_symbols() which fetches
    the full symbol list (prices, volumes, metadata) and stores them
    in the brsapi_symbol_snapshots table.
    """
    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client, close_client
        from brsapi.config import BrsApiEndpoints
        from brsapi.parsers import TsetmcParser
        from brsapi.models import SymbolSnapshotModel
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
            await close_client()


class SyncQuotesJob(BaseJob):
    """Sync all quotes (price/volume data) via BrsApi.

    Uses the same ALL_SYMBOLS endpoint as SyncInstrumentsJob since
    BrsApi returns price/volume/quotes in the same snapshot call.
    Also fetches indices for market-wide quote context.
    """
    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client, close_client
        from brsapi.config import BrsApiEndpoints
        from brsapi.parsers import TsetmcParser
        from brsapi.models import SymbolSnapshotModel, IndexValueModel
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        try:
            symbols_count = 0
            indices_count = 0
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                # Sync all symbols (includes price/volume)
                symbols_report = await service.sync(
                    endpoint=BrsApiEndpoints.ALL_SYMBOLS,
                    parser=TsetmcParser.parse_all_symbols,
                    model_class=SymbolSnapshotModel,
                    params={"type": "1"},
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
            await close_client()


class SyncCodalJob(BaseJob):
    """Sync Codal announcements via BrsApi.

    Delegates to BrsApiSyncService.sync_codal() which fetches
    recent announcements and stores them in brsapi_codal_announcements.
    """
    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client, close_client
        from brsapi.config import BrsApiEndpoints
        from brsapi.parsers import CodalParser
        from brsapi.models import CodalAnnouncementModel
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
            await close_client()


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
