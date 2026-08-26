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
