from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.ids import new_id
from core.logging import get_logger
from orchestration.contracts import Step, Workflow
from orchestration.steps import (
    FetchDataStep,
    PersistDataStep,
    TransformDataStep,
    ValidateDataStep,
)

logger = get_logger("orchestration.training_flow")


class ModelTrainingFlow:
    def __init__(self) -> None:
        self._custom_steps: list[Step] = []

    def add_custom_step(self, step: Step) -> None:
        self._custom_steps.append(step)

    def create_flow(
        self,
        config: dict[str, Any],
        data_provider: Any = None,
        feature_fn: Callable[[Any], Any] | None = None,
        trainer: Any = None,
        evaluator: Any = None,
        registry: Any = None,
    ) -> Workflow:
        workflow_id = new_id()
        steps: list[Step] = []

        load_step = FetchDataStep(
            name="load_data",
            provider=data_provider,
            params={
                "dataset": config.get("dataset", "default"),
                "split": config.get("train_split", 0.8),
                "features": config.get("features", []),
                "target": config.get("target", "target"),
            },
        )
        steps.append(load_step)

        default_feature_fn = feature_fn or self._default_feature_engineering
        feature_step = TransformDataStep(
            name="feature_engineering",
            transform_fn=default_feature_fn,
            input_key="load_data_result",
        )
        steps.append(feature_step)

        def train_model_fn(data: Any) -> Any:
            if trainer and hasattr(trainer, "train"):
                model = trainer.train(data, config)
                return {
                    "model": model,
                    "config": config,
                    "training_data_shape": (len(data) if isinstance(data, (list, dict)) else 0),
                }
            return {
                "model": None,
                "config": config,
                "status": "no_trainer_provided",
            }

        train_step = TransformDataStep(
            name="train_model",
            transform_fn=train_model_fn,
            input_key="feature_engineering_result",
        )
        steps.append(train_step)

        def evaluate_model_fn(data: Any) -> Any:
            model_info = data
            if evaluator and hasattr(evaluator, "evaluate"):
                metrics = evaluator.evaluate(model_info)
                return {
                    "model_info": model_info,
                    "metrics": metrics,
                    "passed": metrics.get("accuracy", 0) >= config.get("min_accuracy", 0.0),
                }
            return {
                "model_info": model_info,
                "metrics": {},
                "passed": True,
                "status": "no_evaluator_provided",
            }

        eval_step = TransformDataStep(
            name="evaluate_model",
            transform_fn=evaluate_model_fn,
            input_key="train_model_result",
        )
        steps.append(eval_step)

        def validate_model_fn(data: Any) -> bool:
            if isinstance(data, dict):
                return data.get("passed", False)
            return False

        validate_step = ValidateDataStep(
            name="validate_model",
            validator_fn=validate_model_fn,
            input_key="evaluate_model_result",
            error_message="Model validation failed: metrics below threshold",
        )
        steps.append(validate_step)

        def persist_model_fn(data: Any) -> Any:
            if registry and hasattr(registry, "register"):
                model_info = data.get("model_info", {}) if isinstance(data, dict) else data
                model = model_info.get("model") if isinstance(model_info, dict) else None
                model_id = registry.register(
                    model=model,
                    metrics=data.get("metrics", {}),
                    config=config,
                )
                return {"model_id": model_id, "registered": True}
            return {"model_id": None, "registered": False}

        persist_step = PersistDataStep(
            name="register_model",
            repository=registry,
            input_key="evaluate_model_result",
            persist_method="register",
        )
        steps.append(persist_step)

        steps.extend(self._custom_steps)

        class _TrainingWorkflow(Workflow):
            async def execute(self_wf, context: Any) -> Any:
                return context

        workflow = _TrainingWorkflow(
            workflow_id=workflow_id,
            name="model_training",
            steps=steps,
        )
        logger.info(f"Created ModelTrainingFlow workflow {workflow_id} with {len(steps)} steps")
        return workflow

    @staticmethod
    def _default_feature_engineering(data: Any) -> Any:
        if isinstance(data, dict):
            features = data.get("features", data)
            if isinstance(features, list):
                return {"features": features, "engineered": True}
            return {"features": list(features.keys()) if isinstance(features, dict) else features, "engineered": True}
        if isinstance(data, list):
            return {"features": data, "engineered": True}
        return {"features": [], "engineered": True}
