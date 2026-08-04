"""Database row safety helpers.

Small, dependency-free utilities for safely extracting typed values from
raw SQLAlchemy/SQL row tuples. Centralises the repeated
``if not row or row[X] is None: return default`` pattern that was previously
inlined across many services.

Typical usage:

    from core.db_utils import safe_row_float, safe_row_int

    # fetchone() may return None when the result set is empty
    row = result.fetchone()
    if not row:
        return default_total
    total = safe_row_float(row, idx=0, default=0.0)

    # For multi-column SELECT, look up by index
    avg = safe_row_float(row, idx=2)
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

__all__ = [
    "safe_row_float",
    "safe_row_int",
    "safe_row_str",
    "safe_row_value",
    "safe_float",
    "safe_int",
]


def _row_has_index(row: Any, idx: int) -> bool:
    """Return True if row exists and index is in range."""
    if row is None:
        return False
    try:
        return 0 <= idx < len(row)
    except (TypeError, ValueError):
        return False


def safe_row_value(row: Any, idx: int = 0, default: Any = None) -> Any:
    """Safely return ``row[idx]`` if it exists and is not None.

    Args:
        row: A DB row (Sequence / tuple / Row) or None.
        idx: Column index to extract.
        default: Fallback value when row is None, idx out of range, or value is None.

    Returns:
        The value at ``row[idx]`` or ``default`` when extraction is unsafe.

    Note:
        For type-coerced access prefer ``safe_row_float`` / ``safe_row_int`` which
        additionally guard against ``ValueError`` / ``TypeError`` on conversion.
    """
    if not _row_has_index(row, idx):
        return default
    try:
        value = row[idx]
    except (IndexError, KeyError):
        return default
    if value is None:
        return default
    return value


def safe_row_float(row: Any, idx: int = 0, default: float = 0.0) -> float:
    """Return ``float(row[idx])`` when safely convertible, else ``default``.

    Handles all of:
        * row is None or empty result
        * idx out of range
        * underlying value is None
        * ValueError / TypeError during conversion (e.g. '', 'Infinity', NaN-like)
    """
    value = safe_row_value(row, idx, default=None)
    if value is None:
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        result = float(value)
        # Treat NaN / Inf as missing
        if result != result or result in (float("inf"), float("-inf")):
            return default
        return result
    if isinstance(value, str) and not value.strip():
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_row_str(row: Any, idx: int = 0, default: str = "") -> str:
    """Return ``str(row[idx])`` when safely convertible, else ``default``.

    Handles all of:
        * row is None or empty result
        * idx out of range
        * underlying value is None
        * non-string/None values are converted via ``str()``

    Returns:
        The string value at ``row[idx]`` or ``default``. Never returns ``None``.
        If you need to distinguish None from empty string, use ``safe_row_value``.

    Example:
        >>> safe_row_str(("ABC", 123, None), idx=0)
        'ABC'
        >>> safe_row_str("ABC", idx=5, default="N/A")
        'N/A'
        >>> safe_row_str(("",), idx=0, default="N/A")
        ''
    """
    value = safe_row_value(row, idx, default=None)
    if value is None:
        return default
    return str(value)


def safe_row_int(row: Any, idx: int = 0, default: int = 0) -> int:
    """Return ``int(row[idx])`` when safely convertible, else ``default``.

    Strings are coerced via ``float`` first to gracefully handle numeric strings
    like ``"123"`` or ``"123.0"``. Empty strings and None fall back to ``default``.
    """
    value = safe_row_value(row, idx, default=None)
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return default
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return int(float(stripped))
        except (TypeError, ValueError):
            return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Individual value helpers (for dict.get(), scalar values)
# ---------------------------------------------------------------------------


def safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert a single value to float, returning ``default`` on failure.

    Handles None, empty string, 'Infinity', NaN, Inf, and conversion errors.
    This is the consolidated version of the ``_safe_float`` helpers previously
    duplicated in symbol_detail_service, stock_assistant_service, market_watch,
    and library_parsers.

    Example:
        >>> safe_float("1,234")  # doctest: +SKIP
        1234.0
        >>> safe_float(None)
        0.0
        >>> safe_float("", default=None)

    """
    if val is None:
        return default
    if isinstance(val, bool):
        return float(val)
    if isinstance(val, (int, float)):
        result = float(val)
        if result != result or result in (float("inf"), float("-inf")):
            return default
        return result
    if isinstance(val, str):
        stripped = val.strip()
        if not stripped or stripped == "Infinity":
            return default
        # Remove thousand separators (1,234 -> 1234)
        val_str = stripped.replace(",", "").replace("٬", "")
        try:
            return float(val_str)
        except (ValueError, TypeError):
            return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val: Any, default: int = 0) -> int:
    """Safely convert a single value to int, returning ``default`` on failure.

    Handles None, empty string, and conversion errors. Strings are coerced
    via ``float`` to handle numeric strings like ``"123.0"`` or ``"123"``.
    This is the consolidated version of the ``_safe_int`` helpers previously
    duplicated in symbol_detail_service, stock_assistant_service, market_watch,
    and library_parsers.

    Example:
        >>> safe_int("123.0")
        123
        >>> safe_int(None, default=0)
        0
    """
    if val is None:
        return default
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        if val != val or val in (float("inf"), float("-inf")):
            return default
        return int(val)
    if isinstance(val, str):
        stripped = val.strip()
        if not stripped:
            return default
        try:
            return int(float(stripped))
        except (ValueError, TypeError):
            return default
    try:
        return int(float(val))  # via float for robust conversion
    except (ValueError, TypeError):
        return default


def is_row_empty(row: Any) -> bool:
    """Return True if row is None or has no columns."""
    if row is None:
        return True
    try:
        return len(row) == 0
    except TypeError:
        return True


# Re-export typing aliases for older code that imported with Sequence
RowLike = Sequence[Any] | None
