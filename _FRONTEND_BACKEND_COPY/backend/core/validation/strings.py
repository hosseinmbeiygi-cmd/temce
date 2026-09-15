from __future__ import annotations

import re
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


def validate_email(email: str) -> None:
    pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    if not pattern.match(email):
        raise ValueError("Invalid email format")


def validate_mobile(mobile: str) -> None:
    pattern = re.compile(r"^09\d{9}$")
    if not pattern.match(mobile):
        raise ValueError("Invalid mobile number format")


def validate_url(url: str) -> None:
    pattern = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
    if not pattern.match(url):
        raise ValueError("Invalid URL format")


def validate_alphanumeric(value: str, field_name: str = "value") -> None:
    if not value.isalnum():
        raise ValueError(f"{field_name} must be alphanumeric")


def validate_no_whitespace(value: str, field_name: str = "value") -> None:
    if re.search(r"\s", value):
        raise ValueError(f"{field_name} must not contain whitespace")
