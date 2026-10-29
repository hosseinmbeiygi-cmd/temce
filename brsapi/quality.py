"""Data-quality rules for the BrsApi history tables.

Why this module exists
======================
Three different date/time concepts live side by side in the history tables and
none of them was written down in code before:

``date``        Jalali (Shamsi) **market/trading date** from the provider
                (``history_daily[].date`` for gold/coin/FX, ``Nav.php.date`` for
                fund NAV). Stored as text, and historically in two separators
                (``1405-06-23`` *and* ``1405/05/01``) — ISSUE-127.
``fetched_at``  client wall clock when the HTTP payload that carried the bar was
                received. It is *not* the market date; a backfill in October can
                legitimately write a 1404 bar.
``created_at``  DB ``now()`` when the row was inserted. Same class as
                ``fetched_at`` but stamped by the database, not the worker.

Anything that filters "last N days" must use ``date`` (converted to Gregorian),
never ``fetched_at``/``created_at`` — a bulk backfill makes every historical bar
look brand new.

What is here
============
* :func:`normalize_jalali_date` / :func:`jalali_to_gregorian` — one deterministic
  Jalali parse used by ingestion, freshness and tests (Persian/Arabic digits,
  ``/`` or ``-`` separators, zero padding, year/range validation).
* :func:`daily_bar_issues` — the single definition of a *valid* daily OHLC bar.
* :func:`history_quality_queries` — **read-only** ``SELECT`` statements for the
  data-quality dashboard (no ``UPDATE``/``DELETE``/``TRUNCATE`` is generated,
  ever).

This module never mutates, repairs or deletes data: invalid bars are reported so
a caller can quarantine (skip) them, existing rows are left exactly as they are.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

__all__ = [
    "ISSUE_CLOSE_OUTSIDE_RANGE",
    "ISSUE_HIGH_BELOW_LOW",
    "ISSUE_MISSING_CLOSE",
    "ISSUE_NON_FINITE",
    "ISSUE_NON_POSITIVE",
    "ISSUE_OPEN_OUTSIDE_RANGE",
    "OHLC_HISTORY_TABLES",
    "NAV_HISTORY_TABLES",
    "daily_bar_issues",
    "history_quality_queries",
    "is_valid_daily_bar",
    "jalali_to_gregorian",
    "normalize_jalali_date",
]

# ── Issue codes ───────────────────────────────────────────────────────
# Stable strings: they end up in logs and in the quality report, so a dashboard
# can count them without parsing prose.

ISSUE_MISSING_CLOSE = "missing_close"
ISSUE_NON_FINITE = "non_finite"
ISSUE_NON_POSITIVE = "non_positive"
ISSUE_HIGH_BELOW_LOW = "high_below_low"
ISSUE_CLOSE_OUTSIDE_RANGE = "close_outside_range"
ISSUE_OPEN_OUTSIDE_RANGE = "open_outside_range"

# ── Tables covered by this module ─────────────────────────────────────

OHLC_HISTORY_TABLES: tuple[str, ...] = (
    "brsapi_gold_coin_history",
    "brsapi_gold_currency_pro_daily_history",
)

NAV_HISTORY_TABLES: tuple[str, ...] = ("brsapi_nav_records",)

# ── Jalali dates ──────────────────────────────────────────────────────

# Persian (۰-۹, U+06F0-06F9) and Arabic-Indic (٠-٩, U+0660-0669) digits.
_DIGIT_TRANS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

# Jalali years in scope. Gregorian years (~2000) and the provider's stray `1348`
# rows are handled explicitly: 1348 is a valid Jalali year, 2026 is not.
_MIN_JALALI_YEAR = 1200
_MAX_JALALI_YEAR = 1599

# SQL-side digit/separator normalisation used by the diagnostics and by the
# freshness probe. `translate` is plain Postgres and needs no extension.
SQL_JALALI_NORMALIZE = "REPLACE(TRANSLATE({column}, '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'), '/', '-')"


def normalize_jalali_date(value: Any) -> str | None:
    """Return a zero-padded Jalali ``YYYY-MM-DD`` string, or ``None``.

    Accepts the formats the provider actually emits (``1405-06-23``,
    ``1405/05/01``, ``۱۴۰۵/۰۵/۰۳``, ``1405.06.23``, ints in ``date``/``datetime``)
    and rejects anything that is not a Jalali date in ``1200..1599``.

    ``None`` means "this is not a usable market date" — callers must not invent
    one (no ``today`` fallback: a bar with an unknown date cannot be placed on a
    time axis, and stamping it with the ingestion date is exactly ISSUE-127).
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return _format_jalali(value.year, value.month, value.day)

    text = str(value).strip().translate(_DIGIT_TRANS).strip()
    if not text:
        return None
    text = text.replace("/", "-").replace(".", "-")
    parts = text.split("-")
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(part) for part in parts)
    except (TypeError, ValueError):
        return None
    return _format_jalali(year, month, day)


def _format_jalali(year: int, month: int, day: int) -> str | None:
    if not _MIN_JALALI_YEAR <= year <= _MAX_JALALI_YEAR:
        return None
    if not 1 <= month <= 12:
        return None
    if not 1 <= day <= 31:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def jalali_to_gregorian(value: Any) -> date | None:
    """Convert a Jalali date to a ``datetime.date`` (Gregorian).

    Returns ``None`` for unparsable input *and* for impossible days
    (``1405-12-31`` in a non-leap year), so a caller can never silently get a
    neighbouring day.
    """
    normalized = normalize_jalali_date(value)
    if normalized is None:
        return None
    try:
        import jdatetime

        year, month, day = (int(part) for part in normalized.split("-"))
        converted = jdatetime.date(year, month, day).togregorian()
    except (ImportError, TypeError, ValueError):
        return None
    return date(converted.year, converted.month, converted.day)


# ── Daily OHLC bar rules ──────────────────────────────────────────────


def daily_bar_issues(
    *,
    close: float | None,
    high: float | None = None,
    low: float | None = None,
    open: float | None = None,  # noqa: A002 — matches the column name `price_open`
) -> tuple[str, ...]:
    """Return the quality issues of one daily bar (empty tuple == valid).

    Rules, in order:

    * ``missing_close``       — no close price: the bar cannot define a series.
    * ``non_finite``          — ``NaN``/``inf``: arithmetic silently poisons sums.
    * ``non_positive``        — a present price ``<= 0`` is never a real quote for
      gold, coin, FX or a fund unit NAV.
    * ``high_below_low``      — ``high < low`` violates the bar's own definition.
    * ``close_outside_range`` / ``open_outside_range`` — a price outside
      ``[low, high]``. Skipped when ``high < low`` (the range is meaningless).

    Zero is reported, never rewritten: fixing a price is a decision for a human
    with the provider's raw payload, not something a validator may do.
    """
    issues: list[str] = []

    if close is None:
        issues.append(ISSUE_MISSING_CLOSE)

    for name, value in (("open", open), ("high", high), ("low", low), ("close", close)):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            issues.append(f"{ISSUE_NON_FINITE}:{name}")
            continue
        if not math.isfinite(value):
            issues.append(f"{ISSUE_NON_FINITE}:{name}")
        elif value <= 0:
            issues.append(f"{ISSUE_NON_POSITIVE}:{name}")

    if high is not None and low is not None and high < low:
        issues.append(ISSUE_HIGH_BELOW_LOW)
        return tuple(issues)

    if high is not None and low is not None:
        if close is not None and (close > high or close < low):
            issues.append(ISSUE_CLOSE_OUTSIDE_RANGE)
        if open is not None and (open > high or open < low):
            issues.append(ISSUE_OPEN_OUTSIDE_RANGE)

    return tuple(issues)


def is_valid_daily_bar(
    *,
    close: float | None,
    high: float | None = None,
    low: float | None = None,
    open: float | None = None,  # noqa: A002
) -> bool:
    """``True`` when :func:`daily_bar_issues` reports nothing."""
    return not daily_bar_issues(close=close, high=high, low=low, open=open)


# ── Read-only diagnostics ─────────────────────────────────────────────

_SQL_NORMALIZED_DATE = SQL_JALALI_NORMALIZE.format(column="date")
_SQL_NON_POSITIVE = "({column} IS NOT NULL AND {column} <= 0)"


def _ohlc_queries(table: str) -> dict[str, str]:
    return {
        "rows": f"SELECT COUNT(*) AS rows FROM {table}",
        "null_close": f"SELECT COUNT(*) AS n FROM {table} WHERE price_close IS NULL",
        "non_positive_price": (
            "SELECT COUNT(*) AS n FROM {t} WHERE {p}".format(
                t=table,
                p=" OR ".join(
                    _SQL_NON_POSITIVE.format(column=c)
                    for c in ("price_open", "price_high", "price_low", "price_close")
                ),
            )
        ),
        "high_below_low": (
            f"SELECT COUNT(*) AS n FROM {table} "
            "WHERE price_high IS NOT NULL AND price_low IS NOT NULL AND price_high < price_low"
        ),
        "close_outside_range": (
            f"SELECT COUNT(*) AS n FROM {table} "
            "WHERE price_high IS NOT NULL AND price_low IS NOT NULL AND price_high >= price_low "
            "AND price_close IS NOT NULL "
            "AND (price_close > price_high OR price_close < price_low)"
        ),
        "open_outside_range": (
            f"SELECT COUNT(*) AS n FROM {table} "
            "WHERE price_high IS NOT NULL AND price_low IS NOT NULL AND price_high >= price_low "
            "AND price_open IS NOT NULL "
            "AND (price_open > price_high OR price_open < price_low)"
        ),
        "slash_separated_date": (
            f"SELECT COUNT(*) AS n FROM {table} WHERE date LIKE '%/%'"
        ),
        "unparsable_date": (
            f"SELECT COUNT(*) AS n FROM {table} "
            f"WHERE {_SQL_NORMALIZED_DATE} !~ '^1[2-5][0-9][0-9]-[0-1][0-9]-[0-3][0-9]$'"
        ),
        "duplicate_symbol_date": (
            f"SELECT symbol, {_SQL_NORMALIZED_DATE} AS trading_date, COUNT(*) AS n "
            f"FROM {table} GROUP BY symbol, {_SQL_NORMALIZED_DATE} HAVING COUNT(*) > 1 "
            "ORDER BY n DESC"
        ),
        "trading_date_span": (
            f"SELECT MIN({_SQL_NORMALIZED_DATE}) AS first_date, "
            f"MAX({_SQL_NORMALIZED_DATE}) AS last_date, "
            f"COUNT(DISTINCT {_SQL_NORMALIZED_DATE}) AS distinct_dates FROM {table}"
        ),
    }


def _nav_queries(table: str) -> dict[str, str]:
    return {
        "rows": f"SELECT COUNT(*) AS rows FROM {table}",
        "null_date": f"SELECT COUNT(*) AS n FROM {table} WHERE date IS NULL OR date = ''",
        "non_positive_nav_issue": (
            f"SELECT COUNT(*) AS n FROM {table} WHERE nav_issue IS NOT NULL AND nav_issue <= 0"
        ),
        "non_positive_nav_redemption": (
            f"SELECT COUNT(*) AS n FROM {table} "
            "WHERE nav_redemption IS NOT NULL AND nav_redemption <= 0"
        ),
        "missing_both_nav": (
            f"SELECT COUNT(*) AS n FROM {table} WHERE nav_issue IS NULL AND nav_redemption IS NULL"
        ),
        "issue_redemption_mismatch": (
            f"SELECT COUNT(*) AS n FROM {table} "
            "WHERE nav_issue > 0 AND nav_redemption > 0 AND nav_issue <> nav_redemption"
        ),
        "unparsable_date": (
            f"SELECT COUNT(*) AS n FROM {table} "
            f"WHERE {_SQL_NORMALIZED_DATE} !~ '^1[2-5][0-9][0-9]-[0-1][0-9]-[0-3][0-9]$'"
        ),
        "duplicate_symbol_date": (
            f"SELECT symbol, {_SQL_NORMALIZED_DATE} AS trading_date, COUNT(*) AS n "
            f"FROM {table} GROUP BY symbol, {_SQL_NORMALIZED_DATE} HAVING COUNT(*) > 1 "
            "ORDER BY n DESC"
        ),
        "trading_date_span": (
            f"SELECT MIN({_SQL_NORMALIZED_DATE}) AS first_date, "
            f"MAX({_SQL_NORMALIZED_DATE}) AS last_date, "
            f"COUNT(DISTINCT {_SQL_NORMALIZED_DATE}) AS distinct_dates FROM {table}"
        ),
    }


def history_quality_queries(table: str) -> dict[str, str]:
    """Read-only diagnostic ``SELECT``s for one history table.

    The table name is whitelisted — nothing else is interpolated — and every
    returned statement is a ``SELECT`` (asserted by the unit tests), so the
    dashboard can run them against a production database without a write path.

    Raises:
        ValueError: the table is not one of :data:`OHLC_HISTORY_TABLES` /
            :data:`NAV_HISTORY_TABLES`.
    """
    if table in OHLC_HISTORY_TABLES:
        return _ohlc_queries(table)
    if table in NAV_HISTORY_TABLES:
        return _nav_queries(table)
    raise ValueError(
        f"no quality queries for {table!r}; "
        f"expected one of {OHLC_HISTORY_TABLES + NAV_HISTORY_TABLES}"
    )
