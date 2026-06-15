from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.codal_service import CodalService

logger = get_logger(__name__)


class CodalIngestionJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        symbols = context.get_param("symbols", [])
        from_date = context.get_param("from_date", "")
        to_date = context.get_param("to_date", "")
        service = CodalService()
        count = 0
        for symbol in symbols:
            result = await service.ingest_codal(symbol, from_date=from_date, to_date=to_date)
            if result.success:
                count += 1
        return JobResult.success_result(job_name=self.name, data={"processed": count})


class CodalSyncJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        days_back = context.get_param("days_back", 7)
        service = CodalService()
        result = await service.sync_recent(days_back=days_back)
        if result.success:
            return JobResult.success_result(job_name=self.name, data=result.data)
        return JobResult.failure(result.error, job_name=self.name)
