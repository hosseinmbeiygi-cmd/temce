from __future__ import annotations

from typing import Any


def validate_positive(value: float | int, field_name: str = "value") -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive, got {value}")


def validate_non_negative(value: float | int, field_name: str = "value") -> None:
    if value < 0:
        raise ValueError(f"{field_name} must not be negative, got {value}")


def validate_range(
    value: float | int, field_name: str, min_val: float | None = None, max_val: float | None = None
) -> None:
    if min_val is not None and value < min_val:
        raise ValueError(f"{field_name} must be >= {min_val}, got {value}")
    if max_val is not None and value > max_val:
        raise ValueError(f"{field_name} must be <= {max_val}, got {value}")


def validate_integer(value: Any, field_name: str = "value") -> None:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer, got {type(value).__name__}")


def validate_decimal_places(value: float, max_places: int, field_name: str = "value") -> None:
    str_val = str(value)
    if "." in str_val:
        places = len(str_val.split(".")[1])
        if places > max_places:
            raise ValueError(f"{field_name} has {places} decimal places, max allowed is {max_places}")


def validate_percentage(value: float, field_name: str = "percentage") -> None:
    validate_range(value, field_name, 0, 100)


def validate_positive_int(value: int, field_name: str = "value") -> None:
    validate_integer(value, field_name)
    validate_positive(float(value), field_name)
