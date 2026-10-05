"""Tests for the corporate-action adjusted indicator read path (migration 0108).

Layers:

* pure SQL/column shaping — the adjusted query must hit the view and the
  ``*_adj`` columns, the raw one must stay equivalent to the pre-0108 loader,
  and ``build_candles`` must keep the oldest-first contract
* source resolution — dial off, view missing, view present, probe caching
* DB-backed parity — while ``daily_adjust_factors`` is empty the adjusted read
  must return *identical* candles to the raw read (so turning the dial on is a
  no-op on a database without events), a synthetic factor must scale exactly
  the affected date, and the nightly lateral enumeration must return exactly
  what the old 70-second ``GROUP BY`` scan returned.

The DB layer is skipped when the view has not been created yet
(``alembic upgrade head`` not applied).
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from core.config import settings
from services import adjusted_price_reader as reader


def _engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    try:
        return create_async_engine(str(settings.database_url))
    except Exception:  # pragma: no cover - environment dependent
        pytest.skip("DB not reachable")


@pytest.fixture(autouse=True)
def _reset_probe_cache():
    """The existence probe is cached per process — keep tests independent."""
    reader.reset_adjusted_source_cache()
    yield
    reader.reset_adjusted_source_cache()


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value

    def fetchall(self):
        return []


class _RecordingSession:
    """Async session stub: counts calls, records SQL, returns one scalar."""

    def __init__(self, value=None, raises: bool = False):
        self.value = value
        self.raises = raises
        self.calls = 0
        self.statements: list[str] = []

    async def execute(self, statement, *_args, **_kwargs):
        self.calls += 1
        self.statements.append(str(statement))
        if self.raises:
            raise RuntimeError("catalog unavailable")
        return _FakeResult(self.value)

    @property
    def last_sql(self) -> str:
        return self.statements[-1] if self.statements else ""


# ── pure: columns / SQL ──────────────────────────────────────────────────


class TestQueryShaping:
    def test_price_column_mapping(self):
        assert reader.price_column("close", adjusted=True) == "price_last_adj"
        assert reader.price_column("close", adjusted=False) == "price_last"
        assert reader.price_column("open", adjusted=True) == "price_first_adj"
        assert reader.price_column("high", adjusted=True) == "price_max_adj"
        assert reader.price_column("low", adjusted=True) == "price_min_adj"

    def test_adjusted_query_reads_view_and_adj_columns(self):
        sql = reader.build_candle_query(reader.ADJUSTED_VIEW, adjusted=True)
        assert f"FROM {reader.ADJUSTED_VIEW} d" in sql
        for col in ("price_first_adj", "price_max_adj", "price_min_adj", "price_last_adj"):
            assert col in sql
        # columns are aliased back to the raw names so build_candles is source-agnostic
        assert "AS price_last" in sql
        assert "ORDER BY d.trade_date DESC LIMIT :lim" in sql

    def test_raw_query_is_the_legacy_shape(self):
        sql = reader.build_candle_query(reader.RAW_SOURCE, adjusted=False)
        assert "FROM daily_history d" in sql
        assert "_adj" not in sql
        assert "price_last IS NOT NULL" in sql
        assert "price_first AS price_first" in sql
        assert "price_last AS price_last" in sql

    def test_volume_and_value_are_never_adjusted(self):
        sql = reader.build_candle_query(reader.ADJUSTED_VIEW, adjusted=True)
        assert "d.trade_volume" in sql and "trade_volume_adj" not in sql


class TestBuildCandles:
    def test_rows_are_returned_oldest_first(self):
        rows = [
            (date(2026, 3, 21), 100, 110, 90, 105, 1000, 5000),
            (date(2026, 3, 20), 90, 100, 80, 95, 900, 4000),
        ]
        candles = reader.build_candles(rows)
        assert [c["date"] for c in candles] == ["2026-03-20", "2026-03-21"]
        assert candles[-1]["close"] == 105.0

    def test_missing_ohlc_legs_fall_back_to_close(self):
        candles = reader.build_candles([(date(2026, 3, 20), None, None, None, 95, None, None)])
        assert candles[0]["open"] == 95.0
        assert candles[0]["high"] == 95.0
        assert candles[0]["low"] == 95.0
        assert candles[0]["volume"] == 0.0
        assert candles[0]["value"] == 0.0

    def test_adjusted_close_is_passed_through_verbatim(self):
        # a 100% capital increase halves pre-ex-date prices: 105 raw → 52.5
        candles = reader.build_candles([(date(2026, 3, 19), 50, 55, 45, 52.5, 1000, 5000)])
        assert candles[0]["close"] == pytest.approx(52.5)


# ── pure: dial + fallback ────────────────────────────────────────────────


class TestSourceResolution:
    async def test_dial_off_uses_raw_without_probing(self, monkeypatch):
        monkeypatch.setattr(settings, "indicator_adjusted_prices", False, raising=False)
        session = _RecordingSession("vw_daily_history_adjusted")
        assert await reader.resolve_price_source(session) == (reader.RAW_SOURCE, False)
        assert session.calls == 0

    async def test_missing_view_falls_back_to_raw(self, monkeypatch):
        monkeypatch.setattr(settings, "indicator_adjusted_prices", True, raising=False)
        session = _RecordingSession(None)
        assert await reader.resolve_price_source(session) == (reader.RAW_SOURCE, False)
        assert session.calls == 1

    async def test_present_view_selects_adjusted(self, monkeypatch):
        monkeypatch.setattr(settings, "indicator_adjusted_prices", True, raising=False)
        session = _RecordingSession("vw_daily_history_adjusted")
        assert await reader.resolve_price_source(session) == (reader.ADJUSTED_VIEW, True)

    async def test_probe_result_is_cached_per_process(self, monkeypatch):
        monkeypatch.setattr(settings, "indicator_adjusted_prices", True, raising=False)
        session = _RecordingSession("vw_daily_history_adjusted")
        await reader.resolve_price_source(session)
        await reader.resolve_price_source(session)
        assert session.calls == 1

        reader.reset_adjusted_source_cache()
        await reader.resolve_price_source(session)
        assert session.calls == 2

    async def test_probe_failure_degrades_to_raw(self, monkeypatch):
        monkeypatch.setattr(settings, "indicator_adjusted_prices", True, raising=False)
        assert await reader.resolve_price_source(
            _RecordingSession(raises=True)
        ) == (reader.RAW_SOURCE, False)

    async def test_explicit_override_bypasses_the_dial(self):
        session = _RecordingSession(None)
        await reader.load_daily_candles(session, "TEST", 5, adjusted=False)
        assert "FROM daily_history d" in session.last_sql and "_adj" not in session.last_sql

        session.statements.clear()
        await reader.load_daily_candles(session, "TEST", 5, adjusted=True)
        assert f"FROM {reader.ADJUSTED_VIEW} d" in session.last_sql


# ── DB-backed ────────────────────────────────────────────────────────────


async def _view_present(conn) -> bool:
    found = (
        await conn.execute(text(f"SELECT to_regclass('public.{reader.ADJUSTED_VIEW}')"))
    ).scalar()
    return found is not None


# Fast symbol pickers. The obvious "GROUP BY symbol ORDER BY count(*)" pick
# reads the whole 10 M-row view (~70 s) — these use the (gregorian_date) index
# instead so the suite stays in the seconds range.
_HOT_SYMBOL = (
    "SELECT symbol FROM brsapi_historical_daily WHERE symbol IS NOT NULL "
    "ORDER BY gregorian_date DESC LIMIT 1"
)
_HOT_REGISTERED_SYMBOL = (
    "SELECT h.symbol, s.id FROM brsapi_historical_daily h JOIN symbols s ON s.symbol = h.symbol "
    "WHERE h.price_last IS NOT NULL ORDER BY h.gregorian_date DESC LIMIT 1"
)
_SOME_SYMBOLS = (
    "SELECT DISTINCT symbol FROM brsapi_historical_daily WHERE symbol IS NOT NULL LIMIT 20"
)


async def _hot_symbol(conn) -> str:
    sym = (await conn.execute(text(_HOT_SYMBOL))).scalar()
    if not sym:
        pytest.skip("no daily_history rows")
    return sym


class TestDatabaseParity:
    async def test_no_factors_means_adjusted_equals_raw(self, monkeypatch):
        """With an empty factor table the new read path is a no-op."""
        eng = _engine()
        try:
            async with eng.connect() as conn:
                if not await _view_present(conn):
                    pytest.skip("vw_daily_history_adjusted missing (run alembic upgrade head)")
                if (await conn.execute(text("SELECT count(*) FROM daily_adjust_factors"))).scalar():
                    pytest.skip("factor table is populated; parity needs the empty state")

                sym = await _hot_symbol(conn)

                monkeypatch.setattr(settings, "indicator_adjusted_prices", False, raising=False)
                raw = await reader.load_daily_candles(conn, sym, 260)

                reader.reset_adjusted_source_cache()
                monkeypatch.setattr(settings, "indicator_adjusted_prices", True, raising=False)
                adjusted = await reader.load_daily_candles(conn, sym, 260)
        finally:
            await eng.dispose()

        assert raw, "no candles loaded"
        assert adjusted == raw

    async def test_synthetic_factor_scales_only_the_affected_date(self, monkeypatch):
        eng = _engine()
        try:
            async with eng.connect() as conn:
                if not await _view_present(conn):
                    pytest.skip("vw_daily_history_adjusted missing (run alembic upgrade head)")

                row = (await conn.execute(text(_HOT_REGISTERED_SYMBOL))).first()
                if not row:
                    pytest.skip("no symbol with a symbols row in daily_history")
                sym, sid = row[0], int(row[1])

                # SQLAlchemy 2.0 autobegins the connection's transaction, so
                # the synthetic factor is undone by rolling that back rather
                # than by opening a nested one.
                try:
                    monkeypatch.setattr(settings, "indicator_adjusted_prices", False, raising=False)
                    raw = await reader.load_daily_candles(conn, sym, 60)

                    target = date.fromisoformat(raw[-1]["date"])
                    await conn.execute(
                        text(
                            "INSERT INTO daily_adjust_factors (symbol_id, trade_date, adj_factor, computed_at) "
                            "VALUES (:sid, :d, 0.5, now()) "
                            "ON CONFLICT (symbol_id, trade_date) DO UPDATE SET adj_factor = 0.5"
                        ),
                        {"sid": sid, "d": target},
                    )

                    reader.reset_adjusted_source_cache()
                    monkeypatch.setattr(settings, "indicator_adjusted_prices", True, raising=False)
                    adjusted = await reader.load_daily_candles(conn, sym, 60)
                finally:
                    await conn.rollback()

                assert len(adjusted) == len(raw)
                # exactly the target date's candles are scaled ...
                scaled = {
                    r["date"]
                    for r, a in zip(raw, adjusted, strict=True)
                    if abs(a["close"] - r["close"] * 0.5) < 1e-9
                }
                assert scaled == {target.isoformat()}
                # ... with every other date byte-identical to the raw read
                for r, a in zip(raw, adjusted, strict=True):
                    if r["date"] == target.isoformat():
                        assert a["close"] == pytest.approx(r["close"] * 0.5)
                        assert a["volume"] == r["volume"]  # volume stays raw
                    else:
                        assert a["close"] == pytest.approx(r["close"])
                        assert a["open"] == pytest.approx(r["open"])

                assert (
                    await conn.execute(text("SELECT count(*) FROM daily_adjust_factors"))
                ).scalar() == 0, "rollback must clean up the synthetic factor"
        finally:
            await eng.dispose()


class TestNightlyBatchEnumeration:
    """The lateral rewrite in ``IndicatorPrecomputeService._select_symbols``."""

    _LATERAL = """
        SELECT s.symbol, l.last_date
        FROM (
            SELECT DISTINCT symbol FROM brsapi_historical_daily
            WHERE symbol IS NOT NULL {symbol_filter}
        ) s
        -- the lateral probes idx_hist_symbol_gregorian once per symbol
        CROSS JOIN LATERAL (
            SELECT h.gregorian_date AS last_date
            FROM brsapi_historical_daily h
            WHERE h.symbol = s.symbol AND h.price_last IS NOT NULL
            ORDER BY h.gregorian_date DESC
            LIMIT 1
        ) l
        ORDER BY s.symbol
        LIMIT :lim
    """

    async def test_lateral_enumeration_matches_group_by(self):
        """Same per-symbol MAX(trade_date) as the full-history GROUP BY scan."""
        eng = _engine()
        try:
            async with eng.connect() as conn:
                syms = [r[0] for r in (await conn.execute(text(_SOME_SYMBOLS))).fetchall()]
                if not syms:
                    pytest.skip("no daily_history rows")

                expected = (
                    await conn.execute(
                        text(
                            "SELECT d.symbol, MAX(d.trade_date) AS last_date FROM daily_history d "
                            "WHERE d.price_last IS NOT NULL AND d.symbol = ANY(:syms) "
                            "GROUP BY d.symbol ORDER BY d.symbol"
                        ),
                        {"syms": syms},
                    )
                ).fetchall()
                got = (
                    await conn.execute(
                        text(self._LATERAL.format(symbol_filter="AND symbol = ANY(:syms)")),
                        {"syms": syms, "lim": len(syms)},
                    )
                ).fetchall()
        finally:
            await eng.dispose()

        assert expected, "sample symbols had no non-null price_last rows"
        assert [(r[0], r[1]) for r in got] == [(r[0], r[1]) for r in expected]

    async def test_lateral_enumeration_honours_the_single_symbol_filter(self):
        eng = _engine()
        try:
            async with eng.connect() as conn:
                sym = await _hot_symbol(conn)
                rows = (
                    await conn.execute(
                        text(self._LATERAL.format(symbol_filter="AND symbol = :symbol")),
                        {"symbol": sym, "lim": 400},
                    )
                ).fetchall()
        finally:
            await eng.dispose()

        assert len(rows) == 1
        assert rows[0][0] == sym
        assert rows[0][1] is not None
