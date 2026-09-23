"""Regression tests for watchlist and market-health query hotspots.

Covers two evidence-backed performance/correctness bugs:

1. WatchlistService._load_enriched_symbols_map scanned the whole
   brsapi_symbol_snapshots table (every 2-minute sync cycle since table
   creation) to enrich <=20 watchlist rows, and WatchlistService.list_items
   ran CREATE TABLE IF NOT EXISTS DDL in the request path on every call.
2. MarketHealthIndex summed volumes/prices across ALL sync cycles in
   history (no fetched_at cutoff), inflating every component. The twin
   service services/iran_fear_greed_index.py fixed this exact bug with a
   UTC-day cutoff; market_health_index.py was never migrated.

These tests use fake sessions that capture the executed SQL text, so they
assert on query shape, not on a live database.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import pytest

from core.result import Result
from services.market_health_index import MarketHealthIndex
from services.watchlist_service import WatchlistService


class FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def fetchall(self) -> list[Any]:
        return self._rows

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    def scalar(self) -> Any:
        return self._rows[0][0] if self._rows else None

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


class SQLCapturingSession:
    """Fake async session that records SQL text + params per execute call.

    `canned` maps a SQL substring to rows returned when that marker matches;
    first matching marker wins, so put more specific markers first.
    """

    def __init__(self, canned: list[tuple[str, list[Any]]] | None = None) -> None:
        self.executed: list[tuple[str, dict[str, Any] | None]] = []
        self.commits = 0
        self._canned = canned or []

    async def execute(self, stmt: Any, params: dict[str, Any] | None = None) -> FakeResult:
        sql = str(stmt)
        self.executed.append((sql, params))
        for marker, rows in self._canned:
            if marker in sql:
                return FakeResult(rows)
        return FakeResult([])

    async def commit(self) -> None:
        self.commits += 1


# ════════════════════════════════════════════════════════════════
# 1. WatchlistService — snapshot query must be cycle-bounded
# ════════════════════════════════════════════════════════════════


class TestWatchlistSnapshotQuery:
    def test_snapshot_query_has_fetched_at_cutoff(self):
        """Enrichment query must limit snapshots to recent cycles instead of
        aggregating every cycle since table creation."""
        session = SQLCapturingSession(
            [
                ("COUNT(*)", [(3,)]),
                ("FROM watchlist", [("فولاد", "", "", 1)]),
            ]
        )
        svc = WatchlistService(session=session)
        asyncio.run(svc.list_items())

        snapshot_queries = [
            sql for sql, _ in session.executed if "brsapi_symbol_snapshots" in sql
        ]
        assert snapshot_queries, "enrichment query never executed"
        assert any(
            "fetched_at >= " in sql
            for sql in snapshot_queries
        ), "snapshot query lacks fetched_at cutoff — scans every sync cycle in history"

    def test_snapshot_query_orders_by_fetched_not_trade_value(self):
        """DISTINCT ON (symbol) must pick the LATEST cycle (fetched_at DESC);
        ORDER BY trade_value DESC picks an arbitrary high-volume historical row."""
        session = SQLCapturingSession(
            [
                ("COUNT(*)", [(3,)]),
                ("FROM watchlist", [("فولاد", "", "", 1)]),
            ]
        )
        svc = WatchlistService(session=session)
        asyncio.run(svc.list_items())

        for sql in (sql for sql, _ in session.executed):
            if "DISTINCT ON" in sql and "brsapi_symbol_snapshots" in sql:
                assert "fetched_at DESC" in sql, (
                    "latest-per-symbol is chosen by trade_value, not recency — "
                    "watchlist shows stale rows from arbitrary old cycles"
                )
                break
        else:
            pytest.fail("no DISTINCT ON snapshot query executed")

    def test_list_items_does_not_run_ddl(self):
        """list_items must not issue CREATE TABLE (DDL churn) per request."""
        session = SQLCapturingSession([("FROM watchlist", [])])
        svc = WatchlistService(session=session)
        result = asyncio.run(svc.list_items())

        assert isinstance(result, Result)
        assert not any("CREATE TABLE" in sql for sql, _ in session.executed), (
            "CREATE TABLE IF NOT EXISTS executed in request path"
        )

    def test_add_symbol_still_creates_table(self):
        """DDL guard: mutation paths may still self-heal the table."""
        session = SQLCapturingSession()
        svc = WatchlistService(session=session)
        asyncio.run(svc.add_symbol("فولاد"))
        assert any("CREATE TABLE" in sql for sql, _ in session.executed)


# ════════════════════════════════════════════════════════════════
# 2. MarketHealthIndex — components must use today's latest cycle
# ════════════════════════════════════════════════════════════════


class TestMarketHealthCutoff:
    def test_all_snapshot_components_have_fetched_at_cutoff(self):
        """Every brsapi_symbol_snapshots aggregate must filter to recent
        cycles; otherwise real/legal flows are inflated by ~every 2-minute
        cycle since table creation."""
        session = SQLCapturingSession(
            [
                ("SUM(buy_real_volume)", [(100.0, 50.0, 60.0, 40.0)]),
                ("large_cap_avg", [(1.0, 2.0, 3.0)]),
                ("block_trades", [(1000, 100)]),
                ("avg_intraday_range", [(1.5,)]),
            ]
        )
        svc = MarketHealthIndex(session=session)
        result = asyncio.run(svc.calculate())

        assert result is not None
        assert 0.0 <= result.overall_score <= 100.0
        snapshot_queries = [
            sql for sql, _ in session.executed if "brsapi_symbol_snapshots" in sql
        ]
        assert snapshot_queries, "no snapshot queries executed"
        unbounded = [sql for sql in snapshot_queries if "fetched_at >= " not in sql]
        assert not unbounded, (
            f"{len(unbounded)}/{len(snapshot_queries)} snapshot queries lack a "
            "fetched_at cutoff — sum every sync cycle in history"
        )

    def test_cutoff_is_datetime_not_string(self):
        """asyncpg raises DataError for string cutoffs against TIMESTAMPTZ;
        params must carry a datetime with tzinfo (see iran_fear_greed_index)."""
        session = SQLCapturingSession(
            [
                ("SUM(buy_real_volume)", [(100.0, 50.0, 60.0, 40.0)]),
                ("large_cap_avg", [(1.0, 2.0, 3.0)]),
                ("block_trades", [(1000, 100)]),
                ("avg_intraday_range", [(1.5,)]),
            ]
        )
        svc = MarketHealthIndex(session=session)
        asyncio.run(svc.calculate())

        for sql, params in session.executed:
            if "brsapi_symbol_snapshots" in sql and "fetched_at >= " in sql:
                assert params is not None and "cutoff_today" in params
                cutoff = params["cutoff_today"]
                assert isinstance(cutoff, datetime), (
                    f"cutoff must be datetime, got {type(cutoff)}"
                )
                assert cutoff.tzinfo is not None, "cutoff must be tz-aware (UTC)"

    def test_distinct_on_latest_per_symbol(self):
        """Aggregates must dedupe to the latest snapshot per symbol per day."""
        session = SQLCapturingSession(
            [
                ("SUM(buy_real_volume)", [(100.0, 50.0, 60.0, 40.0)]),
                ("large_cap_avg", [(1.0, 2.0, 3.0)]),
                ("block_trades", [(1000, 100)]),
                ("avg_intraday_range", [(1.5,)]),
            ]
        )
        svc = MarketHealthIndex(session=session)
        asyncio.run(svc.calculate())

        flow_sqls = [sql for sql, _ in session.executed if "SUM(buy_real_volume)" in sql]
        assert flow_sqls and "DISTINCT ON (symbol)" in flow_sqls[0], (
            "real/legal flow does not dedupe latest snapshot per symbol"
        )
