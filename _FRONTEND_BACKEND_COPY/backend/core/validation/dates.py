from __future__ import annotations

from datetime import UTC, date, datetime

from core.validation import validate_required


def validate_date(value: date | datetime | str, field_name: str = "date") -> None:
    validate_required(value, field_name)


def validate_date_format(value: str, formats: list[str] | None = None) -> None:
    if formats is None:
        formats = ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"]
    for fmt in formats:
        try:
            datetime.strptime(value, fmt)
            return
        except ValueError:
            continue
    raise ValueError(f"Date '{value}' does not match any expected format")


def validate_datetime_iso(value: str) -> None:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Invalid ISO datetime: {value}")


def validate_date_range(start: date | datetime, end: date | datetime) -> None:
    if start > end:
        raise ValueError("start date must be before end date")


def validate_date_not_future(value: date | datetime, field_name: str = "date") -> None:
    if isinstance(value, datetime):
        if value > datetime.now(UTC):
            raise ValueError(f"{field_name} cannot be in the future")
    elif isinstance(value, date) and value > date.today():
        raise ValueError(f"{field_name} cannot be in the future")


def validate_date_not_past(value: date | datetime, field_name: str = "date") -> None:
    if isinstance(value, datetime):
        if value < datetime.now(UTC):
            raise ValueError(f"{field_name} cannot be in the past")
    elif isinstance(value, date) and value < date.today():
        raise ValueError(f"{field_name} cannot be in the past")
