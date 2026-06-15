from __future__ import annotations


def validate_score(score: float) -> bool:
    return 0.0 <= score <= 100.0


def validate_weight(weight: float) -> bool:
    return 0.0 <= weight <= 1.0


def validate_rank(rank: int, total: int) -> bool:
    return 1 <= rank <= total


def validate_percentile(percentile: float) -> bool:
    return 0.0 <= percentile <= 100.0


def validate_factor_value(value: float) -> bool:
    return value >= 0.0


def normalize_score(raw: float, min_val: float, max_val: float) -> float:
    if max_val - min_val == 0:
        return 0.0
    return (raw - min_val) / (max_val - min_val) * 100.0
