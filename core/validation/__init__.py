from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any


def validate_required(value: Any, field_name: str) -> None:
    if value is None:
        raise ValueError(f"{field_name} is required")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def validate_length(value: str, field_name: str, min_len: int = 0, max_len: int | None = None) -> None:
    if len(value) < min_len:
        raise ValueError(f"{field_name} must be at least {min_len} characters")
    if max_len is not None and len(value) > max_len:
        raise ValueError(f"{field_name} must not exceed {max_len} characters")


def validate_range(
    value: float | int, field_name: str, min_val: float | None = None, max_val: float | None = None
) -> None:
    if min_val is not None and value < min_val:
        raise ValueError(f"{field_name} must be >= {min_val}")
    if max_val is not None and value > max_val:
        raise ValueError(f"{field_name} must be <= {max_val}")


IR_SYMBOL_PATTERN = re.compile(r"^[آ-یA-Za-z0-9_-]+$")
ISIN_PATTERN = re.compile(r"^IR[A-Z0-9]{10}$")


def validate_symbol(symbol: str) -> None:
    validate_required(symbol, "symbol")
    if not IR_SYMBOL_PATTERN.match(symbol):
        raise ValueError(f"Invalid symbol format: {symbol}")


def validate_isin(isin: str) -> None:
    validate_required(isin, "isin")
    if not ISIN_PATTERN.match(isin):
        raise ValueError(f"Invalid ISIN format: {isin}")


def validate_date_range(start: date | datetime, end: date | datetime) -> None:
    if start > end:
        raise ValueError("start date must be before end date")


def validate_positive(value: float | int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def validate_non_negative(value: float | int, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} must not be negative")


def validate_choice(value: Any, choices: list[Any], field_name: str) -> None:
    if value not in choices:
        raise ValueError(f"{field_name} must be one of: {choices}")


def validate_email(email: str) -> None:
    pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    if not pattern.match(email):
        raise ValueError("Invalid email format")


def validate_mobile(mobile: str) -> None:
    pattern = re.compile(r"^09\d{9}$")
    if not pattern.match(mobile):
        raise ValueError("Invalid mobile number format")


class Validator:
    def __init__(self) -> None:
        self._errors: list[dict[str, Any]] = []

    def required(self, value: Any, field: str) -> Validator:
        try:
            validate_required(value, field)
        except ValueError as e:
            self._errors.append({"field": field, "message": str(e)})
        return self

    def range(
        self, value: float | int, field: str, min_val: float | None = None, max_val: float | None = None
    ) -> Validator:
        try:
            validate_range(value, field, min_val, max_val)
        except ValueError as e:
            self._errors.append({"field": field, "message": str(e)})
        return self

    def choice(self, value: Any, field: str, choices: list[Any]) -> Validator:
        try:
            validate_choice(value, choices, field)
        except ValueError as e:
            self._errors.append({"field": field, "message": str(e)})
        return self

    def check(self, condition: bool, field: str, message: str) -> Validator:
        if not condition:
            self._errors.append({"field": field, "message": message})
        return self

    def result(self) -> None:
        if self._errors:
            from core.exceptions import ValidationError

            raise ValidationError(errors=self._errors)
