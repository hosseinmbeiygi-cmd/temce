from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.signal_service import SignalService

logger = get_logger(__name__)


class SignalGenerationJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        instrument_ids = context.get_param("instrument_ids", [])
        strategies = context.get_param("strategies", ["ma_cross", "rsi", "macd"])
        service = SignalService()
        count = 0
        for inst_id in instrument_ids:
            result = await service.generate_signals(inst_id, strategies=strategies)
            if result.success:
                count += len(result.value) if isinstance(result.value, list) else 1
        return JobResult.success_result(job_name=self.name, data={"generated": count})


class SignalEvaluationJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        signal_ids = context.get_param("signal_ids", [])
        service = SignalService()
        evaluated = 0
        for signal_id in signal_ids:
            result = await service.evaluate_signal(signal_id)
            if result.success:
                evaluated += 1
        return JobResult.success_result(job_name=self.name, data={"evaluated": evaluated})
