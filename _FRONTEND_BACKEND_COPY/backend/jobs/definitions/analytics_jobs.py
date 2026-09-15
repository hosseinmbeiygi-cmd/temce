from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.analytics_service import AnalyticsService

logger = get_logger(__name__)


class AnalyticsComputationJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        instrument_ids = context.get_param("instrument_ids", [])
        analysis_types = context.get_param("analysis_types", ["volatility", "momentum", "correlation"])
        service = AnalyticsService()
        count = 0
        for inst_id in instrument_ids:
            for atype in analysis_types:
                result = await service.compute(inst_id, analysis_type=atype)
                if result.success:
                    count += 1
        return JobResult.success_result(job_name=self.name, data={"computed": count})


class IndicatorCalculationJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        instrument_ids = context.get_param("instrument_ids", [])
        indicators = context.get_param("indicators", ["sma", "ema", "rsi", "macd", "bbands"])
        service = AnalyticsService()
        count = 0
        for inst_id in instrument_ids:
            for ind in indicators:
                result = await service.calculate_indicator(inst_id, indicator=ind)
                if result.success:
                    count += 1
        return JobResult.success_result(job_name=self.name, data={"calculated": count})
