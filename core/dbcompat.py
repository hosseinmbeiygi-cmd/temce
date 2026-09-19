"""Shared compatibility layer for the three recurring database traps of
this codebase (documented in ``docs/SESSION_REPORT_2026-09-19.md`` §6):

1. **Polyglot PKs** — sibling tables use different id types: ``symbols.id``
   is BIGINT while ``funds.id`` is VARCHAR. A polymorphic column (e.g.
   ``news_tag_symbol_map.resolved_id TEXT``) must be compared with an
   explicitly-cast TEXT expression on the BIGINT side, and asyncpg wants
   the *native* Python type per parameterized column (a str bound to an
   int8 column raises ``DataError`` even behind SQL-side ``CAST``).

2. **Naive timestamps** — most legacy columns are ``timestamp without
   time zone`` (UTC by convention). asyncpg refuses tz-aware datetime
   *parameters* against them (``can't subtract offset-naive and
   offset-aware datetimes``), while the API layer legitimately speaks
   aware datetimes (``?from``/``?to``). Normalize at the DB boundary.

3. **Commit-after-response** — ``core.database.get_session`` commits in
   its teardown *after* the response is sent. A mutation handler that
   relies on that teardown lets an immediate follow-up read (admin UI
   refresh, verify call) race the commit and miss the row. Mutations
   that must be visible to the caller's next request commit explicitly
   before returning (see :func:`commit_now`).

Every helper carries the failure signature it prevents so grep finds the
lesson, not just the fix.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

__all__ = [
    "as_bigint_id",
    "as_text_id",
    "naive_utc",
    "commit_now",
]


# ── trap 1: polyglot primary keys ────────────────────────────────────────


def as_bigint_id(value: str | int, *, what: str = "id") -> int:
    """Coerce a polymorphic id to the native Python ``int`` a BIGINT
    column requires.

    asyncpg re-types parameters per column and ignores SQL-side casts, so
    ``text("... WHERE id = CAST(:i AS BIGINT)")`` still explodes with
    ``TypeError: 'str' object cannot be interpreted as an integer`` when
    bound to ``'123'``. Convert here and bind the int directly.

    Raises ``ValueError`` for non-numeric input so callers can map it to
    a 422-style validation error instead of a 500.
    """
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{what} must be an integer, got {type(value).__name__}")
    try:
        return int(str(value).strip())
    except ValueError:
        raise ValueError(f"{what} must be a valid integer, got {value!r}") from None


def as_text_id(value: Any) -> str:
    """Coerce a polymorphic id to the ``str`` form stored in TEXT columns
    (and required by VARCHAR ``funds.id`` parameters)."""
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


# ── trap 2: naive-timestamp columns ──────────────────────────────────────


def naive_utc(dt: datetime) -> datetime:
    """Normalize any datetime to naive UTC for ``timestamp without time
    zone`` columns (the legacy convention of this schema).

    Aware values convert via ``astimezone(UTC)`` then drop ``tzinfo``;
    naive values pass through untouched (they are already in the column's
    only meaningful reading). Prevents asyncpg's
    ``can't subtract offset-naive and offset-aware datetimes``.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


# ── trap 3: commit-after-response ────────────────────────────────────────


async def commit_now(session: AsyncSession) -> None:
    """Commit *now* instead of relying on ``get_session`` teardown.

    The global dependency commits after the response is sent; anything
    the caller expects to read back in their very next request (admin
    UI list refresh, a verify call) must be durable before the response
    goes out. Failed commits propagate — a silent data-loss path would
    be worse than a failed request.
    """
    await session.commit()
