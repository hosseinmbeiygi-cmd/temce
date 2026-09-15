from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.symbol_service import SymbolService

logger = get_logger(__name__)


class InstrumentSyncJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        source = context.get_param("source", "tsetmc")
        service = SymbolService()
        result = await service.sync_instruments(source=source)
        if result.success:
            return JobResult.success_result(
                job_name=self.name, data={"instruments": len(result.value) if isinstance(result.value, list) else 0}
            )
        return JobResult.failure(result.error, job_name=self.name)


class AliasResolutionJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        symbols = context.get_param("symbols", [])
        service = SymbolService()
        resolved = 0
        for symbol in symbols:
            result = await service.resolve_alias(symbol)
            if result.success:
                resolved += 1
        return JobResult.success_result(job_name=self.name, data={"resolved": resolved})
