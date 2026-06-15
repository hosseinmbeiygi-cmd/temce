from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from ml.models.base import BaseModel
from ml.training.trainer import Trainer
from ml.types import ModelArtifactMeta

logger = get_logger(__name__)


class TrainingService:
    def __init__(self, trainer: Trainer | None = None) -> None:
        self.trainer = trainer or Trainer()
        self._runs: dict[str, dict[str, Any]] = {}

    async def train(self, model: BaseModel, dataset_config: dict[str, Any], **kwargs: Any) -> Result[ModelArtifactMeta]:
        return await self.trainer.train(model, dataset_config, **kwargs)

    async def start_training(
        self, experiment_name: str = "", model_type: str = "xgboost", symbols: list[str] | None = None
    ) -> Result[dict[str, Any]]:
        import uuid

        run_id = uuid.uuid4().hex[:12]
        run = {
            "id": run_id,
            "experiment_name": experiment_name,
            "model_type": model_type,
            "symbols": symbols or [],
            "status": "running",
            "metrics": {},
        }
        self._runs[run_id] = run
        return Result.ok(run)

    async def get_training_status(self, run_id: str) -> Result[dict[str, Any] | None]:
        return Result.ok(self._runs.get(run_id))

    async def list_runs(self) -> Result[list[dict[str, Any]]]:
        return Result.ok(list(self._runs.values()))

    async def cancel_run(self, run_id: str) -> Result[bool]:
        if run_id in self._runs:
            self._runs[run_id]["status"] = "cancelled"
            return Result.ok(True)
        return Result.fail("Run not found")

    async def get_metrics(self, run_id: str) -> Result[dict[str, Any]]:
        run = self._runs.get(run_id)
        if run:
            return Result.ok(run.get("metrics", {}))
        return Result.fail("Run not found")
