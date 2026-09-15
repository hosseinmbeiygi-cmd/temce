from __future__ import annotations

from typing import Any

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from ml.model_loader import _ALGORITHM_PREFIXES
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
            # Auto-refresh the ModelLoader cache after the retrain so the
            # next get_model() call serves the fresh artifact, no restart.
            self._invalidate_after_retrain(model_name, params)
            return JobResult.success_result(job_name=self.name, data={"run_id": result.value})
        return JobResult.failure(result.error, job_name=self.name)

    @staticmethod
    def _invalidate_after_retrain(model_name: str, params: dict[str, Any]) -> None:
        """Evict the freshly-trained model from the ModelLoader LRU cache.

        ``model_name`` is conventionally ``<algorithm>_<symbol>`` (matching the
        artifact dir layout); explicit ``symbol``/``algorithm`` may also be
        passed via ``params``.  Non-fatal on failure.
        """
        symbol = params.get("symbol") if isinstance(params, dict) else None
        algorithm = params.get("algorithm") or params.get("model_type") if isinstance(params, dict) else None

        if not symbol and isinstance(model_name, str):
            # model_name is conventionally ``<algorithm>_<symbol>`` — match the
            # known algorithm prefixes (partition on the first '_' is wrong for
            # names like ``random_forest_وبملت``).
            for maybe_algo in _ALGORITHM_PREFIXES:
                if model_name.startswith(f"{maybe_algo}_"):
                    algorithm = maybe_algo
                    symbol = model_name[len(maybe_algo) + 1 :]
                    break

        if not symbol:
            return
        try:
            from ml.model_loader import get_model_loader

            get_model_loader().invalidate(symbol=symbol, algorithm=algorithm)
            logger.info(
                "ModelLoader cache invalidated for %s/%s (auto-refresh after job %s)",
                symbol,
                algorithm or "all",
                "model_training",
            )
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Could not invalidate ModelLoader cache for %s/%s: %s", symbol, algorithm or "all", e)


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
