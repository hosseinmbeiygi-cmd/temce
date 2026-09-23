#!/usr/bin/env python
"""Backfill/refresh BrsApi tables for the last 250 working days.

Stages (resumable and budget-aware):
  realtime  – refresh current snapshots (gold/currency pro, commodities, crypto, IME, NAV, index, codal)
  gold      – daily OHLC history for gold/coin/currency symbols (last 250 working days)
  crypto    – daily history for crypto symbols
  tsetmc    – resumable market-wide backfills: price, real_legal, candlesticks, shareholders, details
  status    – print per-table coverage (rows / symbols / days / last date)

Usage:
    python scripts/backfill_250_working_days.py --stage realtime
    python scripts/backfill_250_working_days.py --stage gold
    python scripts/backfill_250_working_days.py --stage crypto
    python scripts/backfill_250_working_days.py --stage tsetmc --kind price --symbols 800 --delay 0.4
    python scripts/backfill_250_working_days.py --stage status
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jdatetime  # noqa: E402

import core.database as db  # noqa: E402
from brsapi.budget import get_budget_governor  # noqa: E402
from brsapi.jobs.registry import BRsAPI_SYNC_JOBS, BrsApiJobRegistry  # noqa: E402
from brsapi.services.history_fetch_service import HistoryFetchService  # noqa: E402
from core.database import get_session  # noqa: E402

REALTIME_JOBS = [
    "brsapi_all_symbols",
    "brsapi_index",
    "brsapi_index_farabours",
    "brsapi_gold_currency_pro",
    "brsapi_gold_currency",
    "brsapi_commodities",
    "brsapi_crypto",
    "brsapi_nav",
    "brsapi_ime_funds",
    "brsapi_ime_futures",
    "brsapi_ime_options",
    "brsapi_ime_certificates",
    "brsapi_codal",
    "brsapi_options",
]

WORKING_DAYS = 250
IRAN_WEEKEND = (3, 4)  # Thursday, Friday


def jalali_days_ago(working_days: int) -> str:
    """Return the Jalali date ``working_days`` business days before today."""
    day = jdatetime.date.today()
    remaining = working_days
    while remaining > 0:
        day -= jdatetime.timedelta(days=1)
        if day.weekday() not in IRAN_WEEKEND:
            remaining -= 1
    return day.strftime("%Y-%m-%d")


async def budget_snapshot() -> dict:
    governor = get_budget_governor()
    await governor.initialize()
    stats = await governor.stats()
    return {
        "daily_limit": stats["global"]["daily_limit"],
        "daily_count": stats["global"]["daily_count"],
        "daily_remaining": stats["global"]["daily_remaining"],
        "blocked": stats["block"]["blocked"],
    }


async def stage_realtime(registry: BrsApiJobRegistry) -> None:
    for name in REALTIME_JOBS:
        t0 = time.monotonic()
        try:
            report = await registry.run_job(name, force=True)
            status = "skip" if report is None else ("ok" if report.success else "fail")
            items = 0 if report is None else report.items_count
            print(f"  [{status:4s}] {name:35s} items={items:<8d} {(time.monotonic() - t0):.1f}s")
        except Exception as exc:  # noqa: BLE001
            print(f"  [err ] {name:35s} {type(exc).__name__}: {str(exc)[:100]}")


async def stage_gold(date_start: str, date_end: str | None) -> None:
    async for session in get_session():
        service = HistoryFetchService(session=session)
        reports = await service.sync_gold_currency_history(date_start=date_start, date_end=date_end)
        ok = sum(1 for r in reports if r.success)
        rows = sum(r.record_count or 0 for r in reports)
        print(f"  gold/currency: {ok}/{len(reports)} symbols ok, {rows} rows, window {date_start} → {date_end or 'today'}")
        return


async def stage_crypto(date_start: str, date_end: str | None) -> None:
    async for session in get_session():
        service = HistoryFetchService(session=session)
        reports = await service.sync_crypto_history(date_start=date_start, date_end=date_end)
        ok = sum(1 for r in reports if r.success)
        rows = sum(r.record_count or 0 for r in reports)
        print(f"  crypto: {ok}/{len(reports)} symbols ok, {rows} rows, window {date_start} → {date_end or 'today'}")
        return


async def _run_with_session(registry: BrsApiJobRegistry, name: str, **kwargs: object) -> None:
    from brsapi.client import get_client
    from brsapi.services.sync_service import BrsApiSyncService

    client = await get_client()
    service = BrsApiSyncService(client=client)
    async for session in get_session():
        t0 = time.monotonic()
        if name == "candlesticks":
            report = await registry._run_candlesticks_all(session, service, allow_weekend=True, **kwargs)
        elif name == "shareholders":
            report = await registry._run_shareholders_all(session, service, allow_weekend=True, **kwargs)
        elif name == "details":
            report = await registry._run_symbol_details_all(session, service, allow_weekend=True, **kwargs)
        else:
            report = await registry._run_history_backfill(session, service, kind=name, allow_weekend=True, **kwargs)
        await session.commit()
        if report is None:
            print(f"  [skip] {name} (market closed / no data)")
        else:
            print(
                f"  [{'ok' if report.success else 'fail'}] {name:12s} items={report.items_count} "
                f"{time.monotonic() - t0:.1f}s {report.error or ''}"
            )
        return


async def stage_status() -> None:
    from sqlalchemy import text

    import core.database as database

    assert database.async_session_factory is not None
    tables = [
        ("brsapi_candlesticks", "date"),
        ("brsapi_historical_daily", "date"),
        ("brsapi_historical_real_legal", "date"),
        ("brsapi_shareholder_records", "gregorian_date"),
        ("brsapi_symbol_details", "date"),
        ("brsapi_gold_coin_history", "date"),
        ("brsapi_gold_currency_pro_daily_history", "date"),
        ("brsapi_commodity_prices", "date"),
        ("brsapi_crypto_daily_history", "date"),
        ("brsapi_symbol_snapshots", "gregorian_date"),
        ("brsapi_ime_futures", "date_update"),
        ("brsapi_index_values", "date"),
        ("brsapi_nav_records", "date"),
        ("brsapi_option_snapshots", "gregorian_date"),
        ("brsapi_codal_announcements", "gregorian_date"),
    ]
    async with database.async_session_factory() as session:
        for table, col in tables:
            try:
                rows = (await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar() or 0
                last = (await session.execute(text(f"SELECT max({col})::text FROM {table}"))).scalar() or "—"
                days = (await session.execute(text(f"SELECT count(DISTINCT {col}) FROM {table}"))).scalar() or 0
                print(f"  {table:45s} rows={rows:>10,d} days={days:>6,d} last={last}")
            except Exception as exc:  # noqa: BLE001
                print(f"  {table:45s} ERR {str(exc)[:70]}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=["realtime", "gold", "crypto", "tsetmc", "status", "all"])
    parser.add_argument("--kind", default="all", choices=["price", "real_legal", "candlesticks", "shareholders", "details", "all"])
    parser.add_argument("--symbols", type=int, default=500, help="Max symbols per backfill job")
    parser.add_argument("--delay", type=float, default=0.4, help="Sleep between symbols (seconds)")
    args = parser.parse_args()

    await db.init_database()
    start = jalali_days_ago(WORKING_DAYS)
    print(f"BACKFILL window start (Jalali): {start}  working_days={WORKING_DAYS}")
    print("BUDGET", json.dumps(await budget_snapshot(), ensure_ascii=False))

    registry = BrsApiJobRegistry()
    registry.register_many(BRsAPI_SYNC_JOBS)

    if args.stage in ("realtime", "all"):
        print("STAGE realtime")
        await stage_realtime(registry)
    if args.stage in ("gold", "all"):
        print("STAGE gold")
        await stage_gold(start, None)
    if args.stage in ("crypto", "all"):
        print("STAGE crypto")
        await stage_crypto(start, None)
    if args.stage in ("tsetmc", "all"):
        kinds = ["price", "real_legal", "candlesticks", "shareholders", "details"] if args.kind == "all" else [args.kind]
        for kind in kinds:
            remaining = (await budget_snapshot())["daily_remaining"]
            if remaining < 50:
                print(f"  budget exhausted ({remaining}) — stopping")
                break
            print(f"STAGE tsetmc/{kind} symbols={args.symbols} delay={args.delay}s")
            await _run_with_session(registry, kind, max_symbols=args.symbols, sleep_s=args.delay)
    if args.stage in ("status", "all"):
        print("STAGE status")
        await stage_status()

    print("BUDGET", json.dumps(await budget_snapshot(), ensure_ascii=False))
    await db.close_database()


if __name__ == "__main__":
    asyncio.run(main())
