"""Numeric parsing shared by the BrsApi parsers.

Audit DS-05: the parsers collapsed every missing or unreadable number to
``0``/``0.0``, so a payload without a price published a real-looking zero quote.
These helpers keep ``0`` for a genuine zero and return ``None`` when the value
is absent or not a number.
"""

from __future__ import annotations

from typing import Any

# Persian (۰-۹) and Arabic-Indic (٠-٩) digits.
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).translate(_DIGITS).strip()
    if not text:
        return None
    # Thousands separators (ASCII, Arabic), decimal separator (Arabic).
    text = text.replace(",", "").replace("\u066c", "").replace("\u066b", ".")
    return text


def parse_int(value: Any) -> int | None:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


def parse_float(value: Any) -> float | None:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None
