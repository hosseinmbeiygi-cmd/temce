from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


class ValidationError(Exception):
    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"Validation error on '{field}': {reason}")


def validate_price(value: Any, field: str = "price") -> str | None:
    if value is None:
        return None
    try:
        v = Decimal(str(value))
        if v < 0:
            raise ValidationError(field, "negative value")
        return str(v)
    except (InvalidOperation, TypeError) as e:
        raise ValidationError(field, str(e)) from e


def validate_volume(value: Any, field: str = "volume") -> int:
    if value is None:
        return 0
    try:
        v = int(value)
        if v < 0:
            raise ValidationError(field, "negative volume")
        return v
    except (TypeError, ValueError) as e:
        raise ValidationError(field, str(e)) from e


def validate_instrument_id(value: Any) -> str:
    if not value:
        raise ValidationError("instrument_id", "missing or empty")
    s = str(value).strip()
    if not s:
        raise ValidationError("instrument_id", "empty after strip")
    return s
