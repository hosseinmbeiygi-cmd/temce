from __future__ import annotations

import math


class ForecastMetrics:
    """Forecast metrics for evaluating ML model predictions."""

    def mse(self, actual: list[float], predicted: list[float]) -> float:
        if not actual or not predicted:
            return 0.0
        return sum((a - p) ** 2 for a, p in zip(actual, predicted, strict=False)) / len(actual)

    def rmse(self, actual: list[float], predicted: list[float]) -> float:
        return math.sqrt(self.mse(actual, predicted))

    def mae(self, actual: list[float], predicted: list[float]) -> float:
        if not actual or not predicted:
            return 0.0
        return sum(abs(a - p) for a, p in zip(actual, predicted, strict=False)) / len(actual)

    def r2(self, actual: list[float], predicted: list[float]) -> float:
        if not actual or not predicted:
            return 0.0
        mean_actual = sum(actual) / len(actual)
        ss_res = sum((a - p) ** 2 for a, p in zip(actual, predicted, strict=False))
        ss_tot = sum((a - mean_actual) ** 2 for a in actual)
        if ss_tot == 0:
            return 0.0
        return 1 - ss_res / ss_tot

    def direction_accuracy(self, actual: list[float], predicted: list[float]) -> float:
        if len(actual) < 2:
            return 0.0
        correct = 0
        for i in range(1, len(actual)):
            actual_dir = 1 if actual[i] > actual[i - 1] else -1
            pred_dir = 1 if predicted[i] > predicted[i - 1] else -1
            if actual_dir == pred_dir:
                correct += 1
        return (correct / (len(actual) - 1)) * 100
