from __future__ import annotations

from typing import Any


class ModelSelection:
    def __init__(self, metric: str = "sharpe_ratio") -> None:
        self.metric = metric

    def select_best(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        if not results:
            return {}
        best = max(results, key=lambda r: r.get(self.metric, -1e9))
        return best

    def select_top_n(self, results: list[dict[str, Any]], n: int = 5) -> list[dict[str, Any]]:
        sorted_results = sorted(results, key=lambda r: r.get(self.metric, -1e9), reverse=True)
        return sorted_results[:n]

    def select_by_threshold(self, results: list[dict[str, Any]], min_value: float) -> list[dict[str, Any]]:
        return [r for r in results if r.get(self.metric, -1e9) >= min_value]

    def rank(self, results: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
        sorted_results = sorted(results, key=lambda r: r.get(self.metric, -1e9), reverse=True)
        return [(i + 1, r) for i, r in enumerate(sorted_results)]
