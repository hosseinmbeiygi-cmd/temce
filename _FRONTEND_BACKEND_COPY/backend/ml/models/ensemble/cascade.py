from __future__ import annotations

from typing import Any


class CascadeEnsemble:
    def __init__(self) -> None:
        self._stages: list[Any] = []

    def add_stage(self, model: Any) -> None:
        self._stages.append(model)

    def predict(self, X: Any) -> Any:
        result = X
        for stage in self._stages:
            result = stage.predict(result)
        return result
