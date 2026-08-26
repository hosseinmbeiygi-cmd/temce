"""Unit tests for ``scripts/build_screener_scores.build_daily_scores``.

Covers the full load → calculate → rank → upsert pipeline with mocked
``BatchLoader`` / ``VectorCalculator`` and a real in-memory SQLAlchemy
``Table`` (so the ``pg_insert(...).on_conflict_do_update`` statement is a
real construct — no over-mocking of SQLAlchemy).
"""

from __future__ import annotations

import sys
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import Column, Date, Float, Integer, MetaData, String, Table, Text
from sqlalchemy.sql.elements import TextClause

from scripts.build_screener_scores import build_daily_scores

pytestmark = pytest.mark.asyncio

TRADE_DATE = date(1404, 5, 24)


def _make_table() -> Table:
    return Table(
        "screener_daily_scores",
        MetaData(),
        Column("symbol", String),
        Column("trade_date", Date),
        Column("score_total", Float),
        Column("score_momentum", Float),
        Column("score_value", Float),
        Column("score_growth", Float),
        Column("score_quality", Float),
        Column("score_liquidity", Float),
        Column("score_sentiment", Float),
        Column("rank_in_market", Integer),
        Column("rank_in_industry", Integer),
        Column("percentile_score", Float),
        Column("raw_scores", Text),
        Column("calculated_at", Text),
    )


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.run_sync = AsyncMock(return_value=_make_table())
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


def _sym(symbol: str, score: float, industry: str = "فلزات اساسی", eps: float = 100.0) -> dict[str, Any]:
    return {"symbol": symbol, "eps": eps, "shares_count": 1_000, "industry": industry}


def _calc(symbol: str, score: float, industry: str = "فلزات اساسی") -> dict[str, Any]:
    return {
        "symbol": symbol,
        "final_score": score,
        "score_technical": score,
        "score_valuation": score,
        "score_fundamental": score,
        "score_institutional": score,
        "score_liquidity": score,
        "score_gov_support": score,
        "industry": industry,
    }


def _setup(symbols: list[dict[str, Any]], calc_results: list[dict[str, Any]], profiles: dict | None = None):
    loader = AsyncMock()
    loader.load_all = AsyncMock(return_value={
        "symbols": symbols,
        "daily": {},
        "legal": {},
        "profiles": profiles or {},
        "snapshots": {},
    })
    calc = MagicMock()
    calc.calculate = MagicMock(side_effect=calc_results)
    return loader, calc


def _upsert_rows(session: AsyncMock) -> list[dict[str, Any]]:
    """Return the row lists passed to the chunked upsert executes."""
    rows: list[dict[str, Any]] = []
    for call in session.execute.await_args_list:
        if not isinstance(call.args[0], TextClause) and len(call.args) == 2:
            rows.append(call.args[1])
    return rows


# ──────────────────────────────────────────────
#  build_daily_scores
# ──────────────────────────────────────────────


class TestBuildDailyScores:
    async def test_ranks_and_assigns_percentiles(self) -> None:
        symbols = [_sym("فولاد", 0), _sym("خودرو", 0), _sym("شستا", 0)]
        results = [_calc("فولاد", 80), _calc("خودرو", 60), _calc("شستا", 40)]
        loader, calc = _setup(symbols, results)
        session = _make_session()

        with (
            patch("scripts.build_screener_scores.BatchLoader", return_value=loader),
            patch("scripts.build_screener_scores.VectorCalculator", return_value=calc),
        ):
            stats = await build_daily_scores(session, TRADE_DATE)

        assert stats["symbols"] == 3
        assert stats["rows"] == 3
        assert stats["trade_date"] == "1404-05-24"

        rows = _upsert_rows(session)
        assert len(rows) == 1 and len(rows[0]) == 3
        by_sym = {r["symbol"]: r for r in rows[0]}
        # Rank by final_score desc: فولاد 1, خودرو 2, شستا 3
        assert by_sym["فولاد"]["rank_in_market"] == 1
        assert by_sym["خودرو"]["rank_in_market"] == 2
        assert by_sym["شستا"]["rank_in_market"] == 3
        # percentile = (total - idx) / (total - 1) * 100
        assert by_sym["فولاد"]["percentile_score"] == 100.0
        assert by_sym["خودرو"]["percentile_score"] == 50.0
        assert by_sym["شستا"]["percentile_score"] == 0.0
        # Column mapping
        assert by_sym["فولاد"]["score_total"] == 80
        assert by_sym["فولاد"]["score_momentum"] == 80
        assert by_sym["فولاد"]["trade_date"] == TRADE_DATE
        session.commit.assert_awaited()

    async def test_industry_ranking_groups_symbols(self) -> None:
        symbols = [
            _sym("فولاد", 0, industry="فلزات اساسی"),
            _sym("ذوب", 0, industry="فلزات اساسی"),
            _sym("شپنا", 0, industry="فرآورده‌های نفتی"),
        ]
        results = [
            _calc("فولاد", 90, "فلزات اساسی"),
            _calc("ذوب", 70, "فلزات اساسی"),
            _calc("شپنا", 80, "فرآورده‌های نفتی"),
        ]
        loader, calc = _setup(symbols, results)
        session = _make_session()

        with (
            patch("scripts.build_screener_scores.BatchLoader", return_value=loader),
            patch("scripts.build_screener_scores.VectorCalculator", return_value=calc),
        ):
            await build_daily_scores(session, TRADE_DATE)

        rows = _upsert_rows(session)[0]
        by_sym = {r["symbol"]: r for r in rows}
        assert by_sym["فولاد"]["rank_in_industry"] == 1
        assert by_sym["ذوب"]["rank_in_industry"] == 2
        assert by_sym["شپنا"]["rank_in_industry"] == 1

    async def test_skips_symbols_without_name(self) -> None:
        symbols = [_sym("فولاد", 0), {"eps": 5, "shares_count": 10, "industry": "x"}]
        loader, calc = _setup(symbols, [_calc("فولاد", 60)])
        session = _make_session()

        with (
            patch("scripts.build_screener_scores.BatchLoader", return_value=loader),
            patch("scripts.build_screener_scores.VectorCalculator", return_value=calc),
        ):
            stats = await build_daily_scores(session, TRADE_DATE)

        assert stats["symbols"] == 1
        assert stats["rows"] == 1
        calc.calculate.assert_called_once()

    async def test_eps_overridden_by_profile(self) -> None:
        symbols = [_sym("فولاد", 0, eps=100.0)]
        profiles = {"فولاد": {"eps_current": 500}}
        loader, calc = _setup(symbols, [_calc("فولاد", 50)], profiles=profiles)
        session = _make_session()

        with (
            patch("scripts.build_screener_scores.BatchLoader", return_value=loader),
            patch("scripts.build_screener_scores.VectorCalculator", return_value=calc),
        ):
            await build_daily_scores(session, TRADE_DATE)

        call_kwargs = calc.calculate.call_args.kwargs
        assert call_kwargs["eps"] == 500.0
        assert call_kwargs["symbol"] == "فولاد"

    async def test_upsert_is_chunked(self) -> None:
        symbols = [_sym(f"s{i}", 0) for i in range(5)]
        results = [_calc(f"s{i}", float(50 - i)) for i in range(5)]
        loader, calc = _setup(symbols, results)
        session = _make_session()

        with (
            patch("scripts.build_screener_scores.BatchLoader", return_value=loader),
            patch("scripts.build_screener_scores.VectorCalculator", return_value=calc),
            patch("scripts.build_screener_scores.CHUNK_SIZE", 2),
        ):
            await build_daily_scores(session, TRADE_DATE)

        rows = _upsert_rows(session)
        # 5 rows / chunk of 2 → 3 executes with sizes [2, 2, 1]
        assert [len(r) for r in rows] == [2, 2, 1]

    async def test_writes_sync_log_with_items_count(self) -> None:
        symbols = [_sym("فولاد", 0)]
        loader, calc = _setup(symbols, [_calc("فولاد", 60)])
        session = _make_session()

        with (
            patch("scripts.build_screener_scores.BatchLoader", return_value=loader),
            patch("scripts.build_screener_scores.VectorCalculator", return_value=calc),
        ):
            await build_daily_scores(session, TRADE_DATE)

        log_call = next(
            c for c in session.execute.await_args_list
            if isinstance(c.args[0], TextClause) and "brsapi_sync_log" in str(c.args[0])
        )
        params = log_call.args[1]
        assert params["endpoint"] == "screener_daily_scores"
        assert params["category"] == "screener"
        assert params["items_count"] == 1
        assert "trade_date=1404-05-24" in params["params_snapshot"]

    async def test_sync_log_failure_does_not_crash(self) -> None:
        symbols = [_sym("فولاد", 0)]
        loader, calc = _setup(symbols, [_calc("فولاد", 60)])
        session = _make_session()

        async def _execute(*args: Any, **kwargs: Any) -> Any:
            if isinstance(args[0], TextClause):
                raise RuntimeError("log table missing")
            return MagicMock()

        session.execute = _execute
        with (
            patch("scripts.build_screener_scores.BatchLoader", return_value=loader),
            patch("scripts.build_screener_scores.VectorCalculator", return_value=calc),
        ):
            stats = await build_daily_scores(session, TRADE_DATE)

        assert stats["symbols"] == 1  # log failure tolerated, stats still returned

    async def test_no_symbols_returns_zero_stats(self) -> None:
        loader, calc = _setup([], [])
        session = _make_session()

        with (
            patch("scripts.build_screener_scores.BatchLoader", return_value=loader),
            patch("scripts.build_screener_scores.VectorCalculator", return_value=calc),
        ):
            stats = await build_daily_scores(session, TRADE_DATE)

        assert stats == {"symbols": 0, "rows": 0, "duration_ms": stats["duration_ms"], "trade_date": "1404-05-24"}
        assert not _upsert_rows(session)  # no upsert executed
        # sync log still written (items_count=0)
        log_calls = [c for c in session.execute.await_args_list if isinstance(c.args[0], TextClause)]
        assert any("brsapi_sync_log" in str(c.args[0]) for c in log_calls)


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────


class TestMain:
    async def test_cli_runs_with_date_arg(self) -> None:
        from scripts.build_screener_scores import main

        session = _make_session()
        stats = {"symbols": 3, "rows": 3, "duration_ms": 12.5, "trade_date": "1404-05-24"}

        async def _gen():
            yield session

        with (
            patch.object(sys, "argv", ["build_screener_scores.py", "--date", "1404-05-24"]),
            patch("scripts.build_screener_scores.init_database", new=AsyncMock()),
            patch("scripts.build_screener_scores.get_session", new=_gen),
            patch("scripts.build_screener_scores.build_daily_scores", new=AsyncMock(return_value=stats)) as mock_build,
        ):
            await main()

        mock_build.assert_awaited_once()
        assert mock_build.await_args.args[1] == date(1404, 5, 24)

    async def test_cli_defaults_to_today(self) -> None:
        from scripts.build_screener_scores import main

        session = _make_session()
        stats = {"symbols": 0, "rows": 0, "duration_ms": 1.0, "trade_date": str(date.today())}

        async def _gen():
            yield session

        with (
            patch.object(sys, "argv", ["build_screener_scores.py"]),
            patch("scripts.build_screener_scores.init_database", new=AsyncMock()),
            patch("scripts.build_screener_scores.get_session", new=_gen),
            patch("scripts.build_screener_scores.build_daily_scores", new=AsyncMock(return_value=stats)) as mock_build,
        ):
            await main()

        mock_build.assert_awaited_once()
        assert mock_build.await_args.args[1] == date.today()
