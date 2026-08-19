"""Validate the dual-date SQL functions and trigger against jdatetime.

The conversion functions are installed by ``scripts/install_dual_dates.py``
(migration 0025 runs the same module). These tests re-run that idempotent
installer so they pass on any environment with a reachable PostgreSQL.

Requires a live database (marked ``needs_db`` — auto-skipped otherwise).
"""
from __future__ import annotations

import datetime
import random

import jdatetime
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from scripts.install_dual_dates import FUNCS

try:
    from scripts._db import database_url_async

    DB_URL = database_url_async()
except Exception:  # pragma: no cover
    import os

    DB_URL = os.environ.get("DATABASE_URL")


@pytest.fixture(scope="module")
async def engine():
    engine = create_async_engine(DB_URL)
    async with engine.begin() as c:
        for stmt in FUNCS:
            await c.execute(text(stmt))
    yield engine
    await engine.dispose()


@pytest.mark.needs_db
async def test_shamsi_to_miladi_matches_jdatetime(engine) -> None:
    random.seed(7)
    async with engine.connect() as c:
        for _ in range(200):
            jy = random.randint(1300, 1410)
            jm = random.randint(1, 12)
            jd = random.randint(1, 28)
            expect = jdatetime.date(jy, jm, jd).togregorian()
            got = (
                await c.execute(text("SELECT shamsi_to_miladi(:s)"), {"s": f"{jy}-{jm:02d}-{jd:02d}"})
            ).scalar()
            assert got == expect, f"{jy}-{jm}-{jd}: SQL={got} expected={expect}"


@pytest.mark.needs_db
async def test_miladi_to_shamsi_matches_jdatetime(engine) -> None:
    random.seed(11)
    async with engine.connect() as c:
        for _ in range(200):
            g = datetime.date(random.randint(1995, 2030), random.randint(1, 12), random.randint(1, 28))
            expect = jdatetime.date.fromgregorian(day=g.day, month=g.month, year=g.year)
            exp_s = f"{expect.year}-{expect.month:02d}-{expect.day:02d}"
            got = (await c.execute(text("SELECT miladi_to_shamsi(:d)"), {"d": g})).scalar()
            assert got == exp_s, f"{g}: SQL={got} expected={exp_s}"


@pytest.mark.needs_db
async def test_any_to_miladi_formats(engine) -> None:
    async with engine.connect() as c:
        cases = {
            "1405-05-10": datetime.date(2026, 8, 1),
            "'1405-05-10'": datetime.date(2026, 8, 1),
            "1405/04/24": datetime.date(2026, 7, 15),
            "۱۴۰۵/۰۴/۳۱": datetime.date(2026, 7, 22),
            "2026-07-27T12:19:53Z": datetime.date(2026, 7, 27),
            "2026-07-27 12:19:53+00": datetime.date(2026, 7, 27),
            "1405.04.24": datetime.date(2026, 7, 15),
            "0000-00-00": None,
            "15:49:16": None,
            None: None,
        }
        for v, expect in cases.items():
            got = (await c.execute(text("SELECT any_to_miladi(:v)"), {"v": v})).scalar()
            assert got == expect, f"{v!r}: SQL={got} expected={expect}"


@pytest.mark.needs_db
async def test_trigger_fills_dual_dates(engine) -> None:
    async with engine.begin() as c:
        await c.execute(
            text("CREATE TEMP TABLE _dual_t (id int, trade_date text, gregorian_date date, shamsi_date varchar(10))")
        )
        await c.execute(
            text(
                "INSERT INTO dual_date_columns (table_name, source_column) VALUES ('_dual_t', 'trade_date') "
                "ON CONFLICT (table_name) DO UPDATE SET source_column = EXCLUDED.source_column"
            )
        )
        await c.execute(
            text("CREATE TRIGGER trg_dual_dates BEFORE INSERT OR UPDATE ON _dual_t FOR EACH ROW EXECUTE FUNCTION sync_dual_dates_fn()")
        )
        await c.execute(text("INSERT INTO _dual_t (id, trade_date) VALUES (1, '1405-05-10')"))
        await c.execute(text("INSERT INTO _dual_t (id, trade_date) VALUES (2, '2026-07-27T12:19:53Z')"))
        await c.execute(text("INSERT INTO _dual_t (id, trade_date) VALUES (3, NULL)"))
        rows = (
            await c.execute(text("SELECT id, gregorian_date, shamsi_date FROM _dual_t ORDER BY id"))
        ).fetchall()
        # clean up the temp-table row so the meta table stays tidy
        await c.execute(text("DELETE FROM dual_date_columns WHERE table_name = '_dual_t'"))
    assert rows[0][1] == datetime.date(2026, 8, 1) and rows[0][2] == "1405-05-10"
    assert rows[1][1] == datetime.date(2026, 7, 27) and rows[1][2] == "1405-05-05"
    assert rows[2][1] is None and rows[2][2] is None


@pytest.mark.needs_db
async def test_trigger_resolves_hypertable_chunk(engine) -> None:
    """On TimescaleDB the trigger fires on the chunk (TG_TABLE_NAME = chunk
    name), so sync_dual_dates_fn must resolve the parent hypertable via
    _timescaledb_catalog. Skipped when TimescaleDB is not installed."""
    async with engine.connect() as c:
        has_ts = (
            await c.execute(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')"))
        ).scalar()
    if not has_ts:
        pytest.skip("TimescaleDB not installed")

    async with engine.begin() as c:
        await c.execute(text("DROP TABLE IF EXISTS _dual_ht CASCADE"))
        await c.execute(text("CREATE TABLE _dual_ht (ts timestamptz NOT NULL, v int, gregorian_date date, shamsi_date varchar(10))"))
        await c.execute(text("SELECT create_hypertable('_dual_ht', 'ts', if_not_exists => TRUE)"))
        await c.execute(
            text(
                "INSERT INTO dual_date_columns (table_name, source_column) VALUES ('_dual_ht', 'ts') "
                "ON CONFLICT (table_name) DO UPDATE SET source_column = EXCLUDED.source_column"
            )
        )
        await c.execute(
            text("CREATE TRIGGER trg_dual_dates BEFORE INSERT OR UPDATE ON _dual_ht FOR EACH ROW EXECUTE FUNCTION sync_dual_dates_fn()")
        )
        try:
            await c.execute(
                text("INSERT INTO _dual_ht (ts, v) VALUES ('2026-08-05 10:00:00+03:30', 1)")
            )
            row = (
                await c.execute(text("SELECT gregorian_date, shamsi_date FROM _dual_ht LIMIT 1"))
            ).first()
        finally:
            await c.execute(text("DROP TABLE IF EXISTS _dual_ht CASCADE"))
            await c.execute(text("DELETE FROM dual_date_columns WHERE table_name = '_dual_ht'"))
    assert row[0] == datetime.date(2026, 8, 5) and row[1] == "1405-05-14"
