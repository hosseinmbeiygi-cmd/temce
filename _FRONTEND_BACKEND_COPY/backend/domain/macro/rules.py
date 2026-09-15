from __future__ import annotations


def validate_macro_value(value: float) -> bool:
    return True


def validate_frequency(frequency: str) -> bool:
    return frequency in ("daily", "weekly", "monthly", "quarterly", "yearly")


def validate_unit(unit: str) -> bool:
    return bool(unit)


def is_positive_change(change_pct: float) -> bool:
    return change_pct > 0


def is_negative_change(change_pct: float) -> bool:
    return change_pct < 0
