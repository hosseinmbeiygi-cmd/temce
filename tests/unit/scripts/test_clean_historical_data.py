from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock


class _Row:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def __getitem__(self, key):
        return getattr(self, key)


class _FakeResult:
    def __init__(self, rows):
        # accept a single row OR a list of rows
        self._rows = rows if isinstance(rows, list) else [rows]
        self.rowcount = len(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Session double that returns canned stats and records executed statements."""

    def __init__(self, stats):
        self._stats = stats
        self.executed = []
        # repeat the three canned results so DELETE/log queries also resolve
        self._results_cycle = [
            _FakeResult(stats["first"]),
            _FakeResult(stats["second"]),
            _FakeResult(stats["third"]),
        ]
        self._next_idx = 0
        self.execute = AsyncMock(side_effect=self._do_execute)
        self.commit = AsyncMock()

    async def _do_execute(self, stmt, *params):
        self.executed.append(str(stmt)[:80])
        result = self._results_cycle[self._next_idx % len(self._results_cycle)]
        self._next_idx += 1
        return result


def _make_stats():
    first = _Row(bad_price=5, bad_volume=3)
    second = _Row(dup_rows=4)
    third = _Row(outliers=2)
    return {"first": first, "second": second, "third": third}


def test_dry_run_reports_no_changes():
    from scripts.clean_historical_data import clean_historical_data

    session = _FakeSession(_make_stats())

    async def run():
        return await clean_historical_data(session, dry_run=True)

    stats = asyncio.run(run())

    assert stats["dry_run"] is True
    assert stats["zero_price_rows"] == 5
    assert stats["zero_volume_rows"] == 3
    assert stats["duplicate_date_rows"] == 4
    assert stats["outlier_rows"] == 2
    assert stats["total_candidates"] == 5 + 3 + 4 + 2
    # dry-run: no DELETE executed
    assert not any("DELETE" in e for e in session.executed)


def test_apply_executes_delete_and_commits():
    from scripts.clean_historical_data import clean_historical_data

    session = _FakeSession(_make_stats())

    async def run():
        return await clean_historical_data(session, dry_run=False)

    stats = asyncio.run(run())

    assert stats["dry_run"] is False
    assert any("DELETE" in e for e in session.executed)
    session.commit.assert_awaited()


def test_symbol_scope_passes_filter():
    from scripts.clean_historical_data import clean_historical_data

    session = _FakeSession(_make_stats())

    async def run():
        return await clean_historical_data(session, dry_run=True, symbols=["فولاد"])

    stats = asyncio.run(run())
    assert stats["total_candidates"] >= 0
    # a params dict with a syms filter was passed
    assert any("syms" in str(c.args) for c in session.execute.await_args_list)
