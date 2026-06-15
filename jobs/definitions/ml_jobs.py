from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.inference_service import InferenceService
from services.training_service import TrainingService

logger = get_logger(__name__)


class ModelTrainingJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        model_name = context.get_param("model_name", "default")
        dataset_id = context.get_param("dataset_id", "")
        params = context.get_param("params", {})
        service = TrainingService()
        result = await service.train(model_name=model_name, dataset_id=dataset_id, params=params)
        if result.success:
            return JobResult.success_result(job_name=self.name, data={"run_id": result.value})
        return JobResult.failure(result.error, job_name=self.name)


class BatchInferenceJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        model_id = context.get_param("model_id", "")
        instrument_ids = context.get_param("instrument_ids", [])
        service = InferenceService()
        count = 0
        for inst_id in instrument_ids:
            result = await service.predict(model_id=model_id, instrument_id=inst_id)
            if result.success:
                count += 1
        return JobResult.success_result(job_name=self.name, data={"predicted": count})


class ModelEvaluationJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        model_id = context.get_param("model_id", "")
        test_dataset_id = context.get_param("test_dataset_id", "")
        service = TrainingService()
        result = await service.evaluate(model_id=model_id, dataset_id=test_dataset_id)
        if result.success:
            return JobResult.success_result(job_name=self.name, data={"metrics": result.value})
        return JobResult.failure(result.error, job_name=self.name)
