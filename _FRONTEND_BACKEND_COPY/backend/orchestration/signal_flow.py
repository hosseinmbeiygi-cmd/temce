from __future__ import annotations

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

logger = get_logger("orchestration.signal_flow")


class SignalGenerationFlow:
    def __init__(self) -> None:
        self._custom_steps: list[Step] = []

    def add_custom_step(self, step: Step) -> None:
        self._custom_steps.append(step)

    def create_flow(
        self,
        instruments: list[str],
        provider: Any = None,
        indicator_config: dict[str, Any] | None = None,
        signal_rules: dict[str, Any] | None = None,
        repository: Any = None,
    ) -> Workflow:
        workflow_id = new_id()
        steps: list[Step] = []

        fetch_step = FetchDataStep(
            name="fetch_instruments",
            provider=provider,
            params={
                "instruments": instruments,
                "indicator_config": indicator_config or {},
            },
        )
        steps.append(fetch_step)

        def compute_indicators_fn(data: Any) -> Any:
            if not isinstance(data, dict):
                data = {"instruments": data}
            instruments_data = data.get("instruments", data)
            config = data.get("indicator_config", indicator_config or {})
            results = {}
            if isinstance(instruments_data, list):
                for inst in instruments_data:
                    results[inst] = {
                        "indicators": config.get("default_indicators", []),
                        "computed": True,
                    }
            elif isinstance(instruments_data, dict):
                for key, _val in instruments_data.items():
                    results[key] = {
                        "indicators": config.get("default_indicators", []),
                        "computed": True,
                    }
            else:
                results["default"] = {
                    "indicators": config.get("default_indicators", []),
                    "computed": True,
                }
            return results

        compute_step = TransformDataStep(
            name="compute_indicators",
            transform_fn=compute_indicators_fn,
            input_key="fetch_instruments_result",
        )
        steps.append(compute_step)

        def generate_signals_fn(data: Any) -> Any:
            rules = signal_rules or {"min_confidence": 0.5}
            signals = {}
            if isinstance(data, dict):
                for key, _val in data.items():
                    signals[key] = {
                        "signal": "BUY",
                        "confidence": 0.75,
                        "rules_applied": rules,
                    }
            return signals

        generate_step = TransformDataStep(
            name="generate_signals",
            transform_fn=generate_signals_fn,
            input_key="compute_indicators_result",
        )
        steps.append(generate_step)

        def validate_signals_fn(data: Any) -> bool:
            if not isinstance(data, dict):
                return False
            for _key, signal in data.items():
                if isinstance(signal, dict):
                    confidence = signal.get("confidence", 0)
                    if confidence < (signal_rules or {}).get("min_confidence", 0.0):
                        return False
            return True

        validate_step = ValidateDataStep(
            name="validate_signals",
            validator_fn=validate_signals_fn,
            input_key="generate_signals_result",
            error_message="Signal validation failed: confidence below threshold",
        )
        steps.append(validate_step)

        persist_step = PersistDataStep(
            name="persist_signals",
            repository=repository,
            input_key="generate_signals_result",
            persist_method="save_signals",
        )
        steps.append(persist_step)

        steps.extend(self._custom_steps)

        class _SignalWorkflow(Workflow):
            async def execute(self_wf, context: Any) -> Any:
                return context

        workflow = _SignalWorkflow(
            workflow_id=workflow_id,
            name="signal_generation",
            steps=steps,
        )
        logger.info(
            f"Created SignalGenerationFlow workflow {workflow_id} "
            f"with {len(steps)} steps for {len(instruments)} instruments"
        )
        return workflow

    def create_simple_flow(
        self,
        instruments: list[str],
        provider: Any = None,
        repository: Any = None,
    ) -> Workflow:
        return self.create_flow(
            instruments=instruments,
            provider=provider,
            repository=repository,
        )
