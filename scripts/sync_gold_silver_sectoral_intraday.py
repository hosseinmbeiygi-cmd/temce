"""
Sync intraday trades for all GOLD / SILVER / SECTORAL funds
(طلا / نقره / بخشی) up to today's latest available trading day.

Strategy:
  1) Identify symbols from the latest snapshot whose name contains
     "طلا"/"زر"/"نقره"/"بخشی".
  2) Skip ones that already have ticks in brsapi_intraday_trades.
  3) For each remaining fund, walk back from today (last 14 days) and
     sync the first day that returns > 0 records from BrsApi.
  4) After sync, ALSO sync the *latest* available day per symbol
     (since "today" may be a holiday, we want today's data too if it
     exists). The walkback logic already covers that.

Rate limit: 12 req/min for /Tsetmc/Transaction.php. We use a
semaphore of 4 to stay well under the limit and to be polite.
"""

import asyncio
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path

import jdatetime
from sqlalchemy import func, select

from brsapi.models.tsetmc import (
    IntradayTradeModel,
    SymbolSnapshotModel,
)
from brsapi.services.sync_service import BrsApiSyncService
from core import database
from core.time import now_tehran, now_utc

REPORT = Path("data") / "top50_funds_intraday" / "sync_gss.json"
CONCURRENCY = 4
WALKBACK_DAYS = 14


def _jalali_dates_back(n: int) -> list[str]:
    out: list[str] = []
    g = now_tehran().date()
    for i in range(n):
        d = g - timedelta(days=i)
        j = jdatetime.date.fromgregorian(date=d)
        out.append(f"{j.year:04d}-{j.month:02d}-{j.day:02d}")
    return out


async def _classify_funds(s) -> tuple[list[str], list[str], list[str]]:
    subq = (
        select(
            SymbolSnapshotModel.symbol,
            func.max(SymbolSnapshotModel.id).label("mid"),
        )
        .where(SymbolSnapshotModel.sector == "صندوق سرمایه‌گذاری قابل معامله")
        .group_by(SymbolSnapshotModel.symbol)
        .subquery()
    )
    r = await s.execute(
        select(SymbolSnapshotModel.symbol, SymbolSnapshotModel.name)
        .join(subq, SymbolSnapshotModel.id == subq.c.mid)
        .order_by(SymbolSnapshotModel.symbol)
    )
    gold, silver, sectoral = [], [], []
    for sym, name in r.all():
        n = (name or "") + " " + (sym or "")
        if "نقره" in n:
            silver.append(sym)
        elif "طلا" in n or "زر" in n:
            gold.append(sym)
        elif "بخشی" in n:
            sectoral.append(sym)
    return gold, silver, sectoral


async def _missing_for(s, symbols: list[str]) -> list[str]:
    if not symbols:
        return []
    rows = (
        await s.execute(
            select(IntradayTradeModel.symbol, func.count(IntradayTradeModel.id))
            .where(IntradayTradeModel.symbol.in_(symbols))
            .group_by(IntradayTradeModel.symbol)
        )
    ).all()
    have = {s_ for s_, n in rows if n > 0}
    return [sym for sym in symbols if sym not in have]


async def _sync_one(svc: BrsApiSyncService, s, sym: str, dates: list[str]) -> tuple[str, int, str]:
    """Walk back through dates, return (symbol, total_inserted, last_err)."""
    total = 0
    last_err = ""
    for d in dates:
        try:
            r = await svc.sync_transactions(session=s, symbol=sym, date=d)
            if r.success and r.items_count > 0:
                total += r.items_count
                # Continue trying the same day only if we got a small
                # batch (multi-day batches are common with new listings).
                # For our purposes, the first non-empty day is enough.
                break
            elif r.error and "weekend" in r.error.lower():
                # Skip weekends fast.
                continue
            elif r.error:
                last_err = r.error[:120]
        except Exception as e:
            last_err = str(e)[:120]
            # Don't spam on errors; one bad day is enough to record.
    return sym, total, last_err


async def main() -> None:
    await database.init_database()
    factory = database.async_session_factory

    async with factory() as s:
        gold, silver, sectoral = await _classify_funds(s)
        all_syms = gold + silver + sectoral
        print(f"total classified: gold={len(gold)}  silver={len(silver)}  sectoral={len(sectoral)}")
        missing = await _missing_for(s, all_syms)
        print(f"need sync: {len(missing)} funds")
        if not missing:
            print("nothing to do")
            return

    candidate_dates = _jalali_dates_back(WALKBACK_DAYS)
    print(f"candidate dates: {candidate_dates[:5]} ... ({len(candidate_dates)} total)")

    sem = asyncio.Semaphore(CONCURRENCY)
    counters: Counter = Counter()
    failures: list[tuple[str, str]] = []
    progress_lock = asyncio.Lock()
    done = 0

    async def _run(sym: str) -> None:
        nonlocal done
        async with sem, factory() as s:
            svc = BrsApiSyncService(session=s)
            sym_, n, err = await _sync_one(svc, s, sym, candidate_dates)
            if n > 0:
                counters["ok"] += 1
                counters["ticks"] += n
            else:
                counters["empty"] += 1
            if err:
                failures.append((sym_, err))
            async with progress_lock:
                done += 1
                if done % 10 == 0 or done == len(missing):
                    print(
                        f"  [{done}/{len(missing)}] ok={counters['ok']} "
                        f"empty={counters['empty']} ticks={counters['ticks']}"
                    )

    await asyncio.gather(*[_run(s) for s in missing])

    # Verify final coverage.
    async with factory() as s:
        still_missing = await _missing_for(s, all_syms)

    report = {
        "ran_at": now_utc().isoformat(),
        "classified": {"gold": len(gold), "silver": len(silver), "sectoral": len(sectoral)},
        "attempted": len(missing),
        "synced_ok": counters["ok"],
        "synced_empty": counters["empty"],
        "ticks_inserted": counters["ticks"],
        "failures": failures[:50],
        "still_missing": still_missing,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {REPORT}")
    print(
        f"summary: synced_ok={counters['ok']}  empty={counters['empty']}  "
        f"ticks={counters['ticks']}  still_missing={len(still_missing)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
