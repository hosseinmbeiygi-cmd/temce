from __future__ import annotations

from typing import Any

from core.exceptions import AppError


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed", errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message=message, code="VALIDATION_ERROR", details={"errors": errors or []})


class RequiredFieldError(ValidationError):
    def __init__(self, field: str = "") -> None:
        super().__init__(message=f"Field '{field}' is required", errors=[{"field": field, "message": "required"}])


class InvalidFormatError(ValidationError):
    def __init__(self, field: str = "", expected: str = "") -> None:
        msg = f"Invalid format for '{field}'" + (f", expected {expected}" if expected else "")
        super().__init__(message=msg, errors=[{"field": field, "message": f"invalid_format:{expected}"}])


class OutOfRangeError(ValidationError):
    def __init__(self, field: str = "", min_val: float | None = None, max_val: float | None = None) -> None:
        super().__init__(
            message=f"Field '{field}' out of range",
            errors=[{"field": field, "message": f"out_of_range:min={min_val},max={max_val}"}],
        )


class ConstraintViolationError(ValidationError):
    def __init__(self, message: str = "Constraint violation", constraint: str | None = None) -> None:
        super().__init__(message=message, errors=[{"message": f"constraint:{constraint}"}])
