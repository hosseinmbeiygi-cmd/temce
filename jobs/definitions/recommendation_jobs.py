from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.recommendation_service import RecommendationService

logger = get_logger(__name__)


class RecommendationGenerationJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        instrument_ids = context.get_param("instrument_ids", [])
        service = RecommendationService()
        count = 0
        for inst_id in instrument_ids:
            result = await service.generate_recommendation(inst_id)
            if result.success:
                count += 1
        return JobResult.success_result(job_name=self.name, data={"generated": count})


class RecommendationEvaluationJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        rec_ids = context.get_param("recommendation_ids", [])
        service = RecommendationService()
        evaluated = 0
        for rec_id in rec_ids:
            result = await service.evaluate(rec_id)
            if result.success:
                evaluated += 1
        return JobResult.success_result(job_name=self.name, data={"evaluated": evaluated})
