from __future__ import annotations


def validate_index_value(value: float) -> bool:
    return value >= 0


def validate_weight(weight: float) -> bool:
    return 0.0 <= weight <= 1.0


def validate_total_weight(weights: list[float]) -> bool:
    return abs(sum(weights) - 1.0) < 0.001 if weights else True


def is_positive_change(change_pct: float) -> bool:
    return change_pct > 0


def is_negative_change(change_pct: float) -> bool:
    return change_pct < 0
