"""Tests for the corporate-action adjusted indicator read path (0108/0109).

Layers:

* pure SQL/row shaping — the adjusted query must read the view and order by
  the *indexed* Shamsi date while projecting the derived Gregorian date; the
  raw query must stay the pre-0108 loader; ``build_candles`` must keep the
  oldest-first contract and expose both calendars
* source resolution — dial off, view missing, view present, probe caching
* DB-backed:
  * ``jalali_to_gregorian`` (SQL) matches ``jdatetime`` (Python) exactly, and
    returns NULL for illegal dates
  * with an empty factor table every adjusted price equals the raw one for the
    same ``(symbol, Shamsi date)`` row, and with a synthetic factor exactly the
    affected trade date scales
  * candles are one per **true** trading day (distinct, strictly increasing
    Gregorian dates) — the 0109 bug being that the old axis had 17 distinct
    fetch dates for 5.45 M rows
  * the nightly lateral enumeration returns the true last trade date
"""

from __future__ import annotations

from datetime import date

import jdatetime
import pytest
from sqlalchemy import text

from core.config import settings
from services import adjusted_price_reader as reader


def _python_convert(jalali: str) -> str | None:
    """Reference conversion through jdatetime (the project's library)."""
    try:
        y, m, d = (int(p) for p in jalali.split("-"))
        g = jdatetime.date(y, m, d).togregorian()
    except (ValueError, AttributeError):
        return None
    return f"{g.year:04d}-{g.month:02d}-{g.day:02d}"


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


# ── pure: SQL / row shaping ──────────────────────────────────────────────


class TestQueryShaping:
    def test_adjusted_query_reads_view_and_both_calendars(self):
        sql = reader.build_candle_query(reader.ADJUSTED_VIEW, adjusted=True)
        assert f"FROM {reader.ADJUSTED_VIEW} d" in sql
        assert "d.trade_date_shamsi" in sql
        assert "d.trade_date" in sql
        for col in ("price_first_adj", "price_max_adj", "price_min_adj", "price_last_adj"):
            assert col in sql

    def test_adjusted_query_orders_by_the_indexed_shamsi_column(self):
        """Ordering by the derived date costs 113 ms vs 13 ms (see module doc)."""
        sql = reader.build_candle_query(reader.ADJUSTED_VIEW, adjusted=True)
        assert "ORDER BY d.trade_date_shamsi DESC" in sql
        assert "ORDER BY d.trade_date DESC" not in sql
        assert "d.price_last IS NOT NULL" in sql  # filter before the factor join

    def test_raw_query_is_the_pre_0108_loader(self):
        sql = reader.build_candle_query(reader.RAW_SOURCE, adjusted=False)
        assert "FROM daily_history d" in sql
        assert "_adj" not in sql
        assert "NULL AS trade_date_shamsi" in sql
        assert "price_last IS NOT NULL" in sql

    def test_unknown_source_is_a_programming_error(self):
        with pytest.raises(ValueError):
            reader.build_candle_query("nope", adjusted=True)

    def test_volume_and_value_are_never_adjusted(self):
        for sql in (
            reader.build_candle_query(reader.ADJUSTED_VIEW, adjusted=True),
            reader.build_candle_query(reader.RAW_SOURCE, adjusted=False),
        ):
            assert "trade_volume" in sql and "trade_volume_adj" not in sql


class TestBuildCandles:
    _ROW = ("2026-07-19", "1405-04-28", 100, 110, 90, 105, 1000, 5000)

    def test_rows_are_returned_oldest_first_with_both_calendars(self):
        rows = [
            ("2026-07-20", "1405-04-29", 105, 120, 100, 118, 1200, 6000),
            self._ROW,
        ]
        candles = reader.build_candles(rows)
        assert [c["date"] for c in candles] == ["2026-07-19", "2026-07-20"]
        assert [c["date_shamsi"] for c in candles] == ["1405-04-28", "1405-04-29"]
        assert candles[0]["close"] == 105.0

    def test_missing_ohlc_legs_fall_back_to_close(self):
        candles = reader.build_candles([("2026-07-19", "1405-04-28", None, None, None, 95, None, None)])
        assert candles[0]["open"] == 95.0
        assert candles[0]["high"] == 95.0
        assert candles[0]["low"] == 95.0
        assert candles[0]["volume"] == 0.0
        assert candles[0]["value"] == 0.0

    def test_rows_without_a_resolvable_date_are_dropped(self):
        rows = [
            ("2026-07-20", "1405-04-29", 1, 1, 1, 1, 1, 1),
            (None, "1405-13-01", 1, 1, 1, 1, 1, 1),  # illegal Jalali date
        ]
        candles = reader.build_candles(rows)
        assert [c["date"] for c in candles] == ["2026-07-20"]

    def test_raw_mode_has_no_shamsi_date(self):
        candles = reader.build_candles([("2026-09-14", None, 1, 1, 1, 2, 3, 4)])
        assert candles[0]["date_shamsi"] is None

    def test_adjusted_close_is_passed_through_verbatim(self):
        # 100% capital increase halves pre-ex-date prices: 105 raw → 52.5
        candles = reader.build_candles([("2026-07-19", "1405-04-28", 50, 55, 45, 52.5, 1000, 5000)])
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
        assert await reader.resolve_price_source(_RecordingSession(raises=True)) == (
            reader.RAW_SOURCE,
            False,
        )

    async def test_explicit_override_bypasses_the_dial(self):
        session = _RecordingSession(None)
        await reader.load_daily_candles(session, "TEST", 5, adjusted=False)
        assert "FROM daily_history d" in session.last_sql

        await reader.load_daily_candles(session, "TEST", 5, adjusted=True)
        assert f"FROM {reader.ADJUSTED_VIEW} d" in session.last_sql


# ── DB-backed ────────────────────────────────────────────────────────────


async def _view_present(conn) -> bool:
    found = (
        await conn.execute(text(f"SELECT to_regclass('public.{reader.ADJUSTED_VIEW}')"))
    ).scalar()
    return found is not None


# Fast symbol pickers: the obvious "GROUP BY symbol ORDER BY count(*)" reads the
# whole 5.45 M-row view (~70 s); these use the (gregorian_date) index instead.
_HOT_SYMBOL = (
    "SELECT symbol FROM brsapi_historical_daily WHERE symbol IS NOT NULL "
    "ORDER BY gregorian_date DESC LIMIT 1"
)
_HOT_REGISTERED_SYMBOL = (
    "SELECT h.symbol, s.id FROM brsapi_historical_daily h JOIN symbols s ON s.symbol = h.symbol "
    "WHERE h.price_last IS NOT NULL ORDER BY h.gregorian_date DESC LIMIT 1"
)


class TestSqlJalaliConversion:
    async def test_sql_converter_matches_jdatetime(self):
        eng = _engine()
        try:
            async with eng.connect() as conn:
                if not (await conn.execute(text("SELECT to_regproc('jalali_to_gregorian')"))).scalar():
                    pytest.skip("jalali_to_gregorian missing (run alembic upgrade head)")
                samples = [
                    f"{y:04d}-{m:02d}-{d:02d}"
                    for y in range(1375, 1411)
                    for m in range(1, 13)
                    for d in range(1, 32)
                ]
                rows = (
                    await conn.execute(
                        text(
                            "SELECT j, jalali_to_gregorian(j)::text "
                            "FROM unnest(CAST(:js AS text[])) AS j"
                        ),
                        {"js": samples},
                    )
                ).fetchall()
        finally:
            await eng.dispose()

        mismatches = []
        checked = 0
        for jalali, got in rows:
            expect = _python_convert(jalali)
            if expect is None:
                # illegal date: the SQL function must refuse it too
                if got is not None:
                    mismatches.append((jalali, got, None))
                continue
            checked += 1
            if got != expect:
                mismatches.append((jalali, got, expect))

        assert checked > 10_000
        assert mismatches == []

    async def test_leap_esfand_30_resolves_and_illegal_dates_return_null(self):
        eng = _engine()
        try:
            async with eng.connect() as conn:
                if not (await conn.execute(text("SELECT to_regproc('jalali_to_gregorian')"))).scalar():
                    pytest.skip("jalali_to_gregorian missing (run alembic upgrade head)")
                leap = (await conn.execute(text("SELECT jalali_to_gregorian('1403-12-30')::text"))).scalar()
                bad = (
                    await conn.execute(
                        text(
                            "SELECT count(*) FROM unnest(CAST(:js AS text[])) AS j "
                            "WHERE jalali_to_gregorian(j) IS NOT NULL"
                        ),
                        {"js": ["1404-12-30", "1405-13-01", "1405-07-31", "junk", "", "1405-4-28"]},
                    )
                ).scalar()
        finally:
            await eng.dispose()

        assert leap == _python_convert("1403-12-30")
        assert bad == 0


class TestReadPath:
    async def test_candles_are_one_per_true_trading_day(self):
        """The 0109 fix: distinct consecutive trade dates, both calendars."""
        eng = _engine()
        try:
            async with eng.connect() as conn:
                if not await _view_present(conn):
                    pytest.skip("vw_daily_history_adjusted missing (run alembic upgrade head)")
                sym = (await conn.execute(text(_HOT_SYMBOL))).scalar()
                if not sym:
                    pytest.skip("no daily_history rows")
                # how many usable bars the symbol actually has (indexed count)
                available = (
                    await conn.execute(
                        text(
                            "SELECT count(*) FROM brsapi_historical_daily "
                            "WHERE symbol = :s AND price_last IS NOT NULL"
                        ),
                        {"s": sym},
                    )
                ).scalar()
                candles = await reader.load_daily_candles(conn, sym, 320)
        finally:
            await eng.dispose()

        assert len(candles) == min(320, available)
        dates = [c["date"] for c in candles]
        assert dates == sorted(dates), "candles must be oldest-first"
        assert len(set(dates)) == len(dates), "one candle per trading day"
        # both calendars must describe the same day
        for c in candles:
            assert c["date"] == _python_convert(c["date_shamsi"]), f"{c} calendars disagree"

    async def test_adjusted_prices_equal_raw_when_no_factors_exist(self):
        eng = _engine()
        try:
            async with eng.connect() as conn:
                if not await _view_present(conn):
                    pytest.skip("vw_daily_history_adjusted missing (run alembic upgrade head)")
                if (await conn.execute(text("SELECT count(*) FROM daily_adjust_factors"))).scalar():
                    pytest.skip("factor table populated; needs the empty state")
                sym = (await conn.execute(text(_HOT_SYMBOL))).scalar()
                if not sym:
                    pytest.skip("no daily_history rows")
                mismatches = (
                    await conn.execute(
                        text(
                            """
                            SELECT count(*) FROM brsapi_historical_daily h
                            JOIN vw_daily_history_adjusted v
                              ON v.symbol = h.symbol AND v.trade_date_shamsi = h.date
                            WHERE h.symbol = :sym
                              AND (h.price_last IS DISTINCT FROM v.price_last_adj
                                   OR h.price_close IS DISTINCT FROM v.price_close_adj
                                   OR h.trade_volume IS DISTINCT FROM v.trade_volume)
                            """
                        ),
                        {"sym": sym},
                    )
                ).scalar()
        finally:
            await eng.dispose()

        assert mismatches == 0

    async def test_synthetic_factor_scales_exactly_the_affected_trade_date(self, monkeypatch):
        eng = _engine()
        try:
            async with eng.connect() as conn:
                if not await _view_present(conn):
                    pytest.skip("vw_daily_history_adjusted missing (run alembic upgrade head)")
                row = (await conn.execute(text(_HOT_REGISTERED_SYMBOL))).first()
                if not row:
                    pytest.skip("no symbol with a symbols row in daily_history")
                sym, sid = row[0], int(row[1])

                # SQLAlchemy 2.0 autobegins, so the synthetic factor is undone
                # by rolling that transaction back. Target must come from the
                # ADJUSTED series: its dates are the true trade dates the
                # factor table is keyed on (raw mode exposes fetch dates).
                try:
                    before = await reader.load_daily_candles(conn, sym, 60, adjusted=True)
                    if not before:
                        pytest.skip("no adjusted candles for the picked symbol")
                    assert (await conn.execute(text("SELECT count(*) FROM daily_adjust_factors"))).scalar() == 0

                    target = before[-1]["date"]  # newest true trade date (ISO string)
                    await conn.execute(
                        text(
                            "INSERT INTO daily_adjust_factors "
                            "(symbol_id, trade_date, adj_factor, computed_at) "
                            "VALUES (:sid, :d, 0.5, now()) "
                            "ON CONFLICT (symbol_id, trade_date) DO UPDATE SET adj_factor = 0.5"
                        ),
                        {"sid": sid, "d": date.fromisoformat(target)},
                    )
                    after = await reader.load_daily_candles(conn, sym, 60, adjusted=True)
                finally:
                    await conn.rollback()

                assert len(after) == len(before)
                scaled = {
                    a["date"]
                    for a, b in zip(after, before, strict=True)
                    if abs(a["close"] - b["close"] * 0.5) < 1e-9
                }
                assert scaled == {target}, "only the ex-date candle may be scaled"
                for a, b in zip(after, before, strict=True):
                    if a["date"] == target:
                        assert a["close"] == pytest.approx(b["close"] * 0.5)
                        assert a["volume"] == b["volume"]  # volume stays raw
                    else:
                        assert a["close"] == pytest.approx(b["close"])
                        assert a["date_shamsi"] == b["date_shamsi"]

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
        CROSS JOIN LATERAL (
            SELECT jalali_to_gregorian(h.date) AS last_date
            FROM brsapi_historical_daily h
            WHERE h.symbol = s.symbol AND h.price_last IS NOT NULL
            ORDER BY h.date DESC
            LIMIT 1
        ) l
        ORDER BY s.symbol
        LIMIT :lim
    """

    async def test_enumeration_returns_true_last_trade_date(self):
        eng = _engine()
        try:
            async with eng.connect() as conn:
                if not (await conn.execute(text("SELECT to_regproc('jalali_to_gregorian')"))).scalar():
                    pytest.skip("jalali_to_gregorian missing (run alembic upgrade head)")
                rows = (
                    await conn.execute(text(self._LATERAL.format(symbol_filter="")), {"lim": 25})
                ).fetchall()
                if not rows:
                    pytest.skip("no daily_history rows")

                # independent check for each sampled symbol
                expected = {}
                for sym, _last in rows:
                    jalali = (
                        await conn.execute(
                            text(
                                "SELECT date FROM brsapi_historical_daily "
                                "WHERE symbol = :s AND price_last IS NOT NULL "
                                "ORDER BY date DESC LIMIT 1"
                            ),
                            {"s": sym},
                        )
                    ).scalar()
                    expected[sym] = _python_convert(jalali)
        finally:
            await eng.dispose()

        assert len(rows) == 25
        for sym, last_date in rows:
            assert last_date is not None, f"{sym} has no resolvable trade date"
            assert str(last_date) == expected[sym]

    async def test_enumeration_honours_the_single_symbol_filter(self):
        eng = _engine()
        try:
            async with eng.connect() as conn:
                if not (await conn.execute(text("SELECT to_regproc('jalali_to_gregorian')"))).scalar():
                    pytest.skip("jalali_to_gregorian missing (run alembic upgrade head)")
                sym = (await conn.execute(text(_HOT_SYMBOL))).scalar()
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
