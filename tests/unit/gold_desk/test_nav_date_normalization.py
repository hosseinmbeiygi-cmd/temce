"""NAV history queries must compare Jalali dates independent of the separator.

The table stores both ``1405-06-23`` and ``1405/05/01``. A raw string comparison
is wrong in two ways:

* ``'/'`` (0x2F) sorts *above* ``'-'`` (0x2D), so ``MAX(date)`` — and therefore
  "the latest NAV" — could pick an older slash-separated row;
* ``date <= cutoff`` silently drops same-period slash rows, biasing the 7-day
  NAV change.

These tests pin the normalisation at the query level (no database required).
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.gold_desk.nav_checker import (
    _latest_nav,
    _latest_nav_batch,
    _nav_7d_ago,
    _nav_7d_ago_batch,
)


class _Result:
    def first(self) -> None:
        return None

    def all(self) -> list[Any]:
        return []

    def scalars(self) -> _Result:
        return self

    def scalar(self) -> None:
        return None


class _RecordingSession:
    def __init__(self) -> None:
        self.statements: list[str] = []

    async def execute(self, statement: Any) -> _Result:
        self.statements.append(" ".join(str(statement).split()))
        return _Result()


def _run(coro: Any) -> _RecordingSession:
    session = _RecordingSession()
    asyncio.run(coro)
    return session


class TestNavDateKey:
    def test_latest_nav_orders_by_normalized_date(self) -> None:
        session = _RecordingSession()
        asyncio.run(_latest_nav(session, "اطلس"))

        sql = session.statements[0].lower()
        assert "order by replace(" in sql, sql
        # Ordering on the bare column would resurrect the mixed-separator bug.
        assert "order by brsapi_nav_records.date" not in sql, sql

    def test_seven_day_cutoff_uses_normalized_comparison(self) -> None:
        session = _RecordingSession()
        asyncio.run(_nav_7d_ago(session, "اطلس"))

        sql = session.statements[0].lower()
        assert "replace(" in sql
        # No raw comparison against the un-normalised column.
        assert "brsapi_nav_records.date <=" not in sql

    def test_batch_latest_uses_max_on_normalized_date(self) -> None:
        session = _RecordingSession()
        asyncio.run(_latest_nav_batch(session, ["اطلس", "طلا"]))

        sql = session.statements[0].lower()
        assert "max(replace(" in sql, sql
        assert "group by" in sql

    def test_batch_seven_day_cutoff_is_normalized(self) -> None:
        session = _RecordingSession()
        asyncio.run(_nav_7d_ago_batch(session, ["اطلس"]))

        sql = session.statements[0].lower()
        assert "max(replace(" in sql
        assert "replace(brsapi_nav_records.date" in sql
