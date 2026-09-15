from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.quote_service import QuoteService

logger = get_logger(__name__)


class QuoteIngestionJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        symbols = context.get_param("symbols", [])
        source = context.get_param("source", "tsetmc")
        service = QuoteService()
        count = 0
        for symbol in symbols:
            result = await service.ingest_realtime(symbol, source=source)
            if result.success:
                count += 1
        return JobResult.success_result(job_name=self.name, data={"ingested": count, "source": source})


class HistoricalDataJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        symbols = context.get_param("symbols", [])
        start_date = context.get_param("start_date", "")
        end_date = context.get_param("end_date", "")
        service = QuoteService()
        count = 0
        for symbol in symbols:
            result = await service.ingest_historical(symbol, start_date=start_date, end_date=end_date)
            if result.success:
                count += 1
        return JobResult.success_result(job_name=self.name, data={"processed": count, "symbols": len(symbols)})


class RealtimeQuoteJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        symbols = context.get_param("symbols", [])
        service = QuoteService()
        results = []
        for symbol in symbols:
            result = await service.get_realtime(symbol)
            if result.success:
                results.append(result.value)
        return JobResult.success_result(job_name=self.name, data={"quotes": len(results)})
