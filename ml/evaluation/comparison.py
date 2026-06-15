from __future__ import annotations


class ModelComparison:
    def __init__(self) -> None:
        self._results: dict[str, dict[str, float]] = {}

    def add_model_result(self, name: str, metrics: dict[str, float]) -> None:
        self._results[name] = metrics

    def best_model(self, metric: str = "accuracy") -> str:
        return max(self._results, key=lambda k: self._results[k].get(metric, -float("inf")))
