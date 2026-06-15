from __future__ import annotations

from typing import Any


class PredictionPipeline:
    def __init__(self) -> None:
        self._steps: list[tuple[str, Any]] = []

    def add_step(self, name: str, step: Any) -> None:
        self._steps.append((name, step))

    def run(self, input_data: Any) -> Any:
        data = input_data
        for _name, step in self._steps:
            data = step.predict(data) if hasattr(step, "predict") else step.transform(data)
        return data
