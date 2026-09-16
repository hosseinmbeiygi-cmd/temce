"""🏦 Funds sync job — populates the ``funds`` table from BrsApi snapshots.

Unlike live-price sync jobs, this one reads from ``brsapi_symbol_snapshots``
(already synced data) so it does NOT depend on api.brsapi.ir being reachable.
Each known fund symbol is enriched via ``FundService.update_from_brsapi`` and
stored in the ``funds`` table for the funds API/page.
"""

from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)


class FundsSyncJob(BaseJob):
    """Sync all known fund symbols into the ``funds`` table from snapshots."""

    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.services.query_service import BrsApiQueryService
        from core.database import get_session
        from services.fund_service import FundService
        from services.fund_sync_service import KNOWN_FUND_SYMBOLS, FundSyncService

        session_obtained = False
        try:
            async for session in get_session():
                session_obtained = True
                fund_service = FundService(session=session)
                brsapi = BrsApiQueryService(session=session)
                sync = FundSyncService(fund_service=fund_service, brsapi=brsapi)
                report = await sync.sync_all_funds(symbols=KNOWN_FUND_SYMBOLS)

            if not session_obtained:
                return JobResult.failure("Could not obtain DB session", job_name=self._name)

            logger.info("FundsSyncJob: %s", report.summary)
            return JobResult.success_result(
                job_name=self._name,
                data={
                    "total": report.total,
                    "success_count": report.success,
                    "failed_count": report.failed,
                    "errors": report.errors[:20],
                    "duration_ms": round(report.duration_ms, 1),
                },
            )
        except Exception as e:
            logger.exception("FundsSyncJob failed")
            return JobResult.failure(str(e), job_name=self._name)


class FundDiscoveryJob(BaseJob):
    """🔭 Auto-Discovery کامل Universe صندوق‌ها (Zero-Config).

    - بدون هیچ لیست Hardcoded؛ کل صندوق‌های بازار را از Provider کشف می‌کند.
    - هویت کانونی (ISIN > national_id > symbol) + Alias + Capability Matrix.
    - ممیزی در ``fund_ingestion_runs``؛ خطای یک صندوق کل اجرا را متوقف نمی‌کند.
    """

    async def execute(self, context: JobContext) -> JobResult:
        import time

        from core.database import get_session
        from services.fund_discovery import FundDiscoveryService
        from services.fund_read_through import FundReadThroughService

        t0 = time.time()
        session_obtained = False
        try:
            async for session in get_session():
                session_obtained = True
                # Mutex مشترک: جلوگیری از اجرای هم‌زمان کشف در چند ورکر
                svc = FundReadThroughService(session=session)
                async with svc._guarded("universe"):
                    discovery = FundDiscoveryService(session, svc.adapter)
                    funds = await discovery.discover(store_snapshot=True)
                    stats = discovery.last_stats.to_dict() if discovery.last_stats else {}

            if not session_obtained:
                return JobResult.failure("Could not obtain DB session", job_name=self._name)

            stats["duration_ms_job"] = round((time.time() - t0) * 1000, 1)
            logger.info("FundDiscoveryJob: %d funds — %s", len(funds), stats)
            return JobResult.success_result(job_name=self._name, data=stats)
        except Exception as e:
            logger.exception("FundDiscoveryJob failed")
            return JobResult.failure(str(e), job_name=self._name)
