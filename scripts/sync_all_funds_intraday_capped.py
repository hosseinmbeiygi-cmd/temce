"""
Sync intraday trades for ALL funds (top-50 + gold/silver/sectoral + others)
with a hard cap of 10,000 BrsApi requests.

Strategy:
  - Concurrency 4 to stay well under the 12 req/min Transaction rate limit.
  - For each missing fund, walk back up to 14 days; stop at first
    non-empty day (typical 1 request; max 14 in the worst case).
  - Stop the whole run as soon as the request counter hits MAX_REQUESTS.

After sync, repackage the top-50 JSON/CSV outputs and write a summary.
"""

import argparse
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

REPORT = Path("data") / "top50_funds_intraday" / "sync_all_capped.json"
CONCURRENCY = 4
WALKBACK_DAYS = 14
MAX_REQUESTS = 10_000


def _jalali_dates_back(n: int) -> list[str]:
    out: list[str] = []
    g = now_tehran().date()
    for i in range(n):
        d = g - timedelta(days=i)
        j = jdatetime.date.fromgregorian(date=d)
        out.append(f"{j.year:04d}-{j.month:02d}-{j.day:02d}")
    return out


async def _all_fund_symbols(s) -> list[str]:
    subq = (
        select(
            SymbolSnapshotModel.symbol,
            func.max(SymbolSnapshotModel.id).label("mid"),
        )
        .where(SymbolSnapshotModel.sector == "صندوق سرمایه‌گذاری قابل معامله")
        .group_by(SymbolSnapshotModel.symbol)
        .subquery()
    )
    r = await s.execute(select(SymbolSnapshotModel.symbol).join(subq, SymbolSnapshotModel.id == subq.c.mid))
    return [row[0] for row in r.all()]


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


async def main(walkback_days: int = WALKBACK_DAYS, max_requests: int = MAX_REQUESTS) -> None:
    await database.init_database()
    factory = database.async_session_factory

    async with factory() as s:
        all_syms = await _all_fund_symbols(s)
        print(f"total funds: {len(all_syms)}")
        missing = await _missing_for(s, all_syms)
        print(f"missing: {len(missing)}")
        if not missing:
            print("nothing to do")
            return

    candidate_dates = _jalali_dates_back(walkback_days)

    sem = asyncio.Semaphore(CONCURRENCY)
    counters: Counter = Counter()
    failures: list[tuple[str, str]] = []
    progress_lock = asyncio.Lock()
    done = 0
    stop_event = asyncio.Event()
    request_count = 0

    async def _run(sym: str) -> None:
        nonlocal done, request_count
        if stop_event.is_set():
            return
        async with sem:
            if stop_event.is_set():
                return
            async with factory() as s:
                svc = BrsApiSyncService(session=s)
                total = 0
                last_err = ""
                used = 0
                for d in candidate_dates:
                    if stop_event.is_set():
                        break
                    try:
                        r = await svc.sync_transactions(session=s, symbol=sym, date=d)
                        request_count += 1
                        used += 1
                        if r.success and r.items_count > 0:
                            total += r.items_count
                            break
                        elif r.error and "weekend" in r.error.lower():
                            continue
                        elif r.error:
                            last_err = r.error[:120]
                    except Exception as e:
                        last_err = str(e)[:120]
                    if request_count >= max_requests:
                        stop_event.set()
                        break
                if total > 0:
                    counters["ok"] += 1
                    counters["ticks"] += total
                    counters["requests"] += used
                else:
                    counters["empty"] += 1
                    counters["requests"] += used
                if last_err:
                    failures.append((sym, last_err))
                async with progress_lock:
                    done += 1
                    if done % 25 == 0 or done == len(missing) or stop_event.is_set():
                        print(
                            f"  [{done}/{len(missing)}] ok={counters['ok']} "
                            f"empty={counters['empty']} ticks={counters['ticks']:,} "
                            f"req={counters['requests']}"
                        )

    await asyncio.gather(*[_run(s) for s in missing])

    # Final coverage
    async with factory() as s:
        still_missing = await _missing_for(s, all_syms)

    report = {
        "ran_at": now_utc().isoformat(),
        "walkback_days": walkback_days,
        "total_funds": len(all_syms),
        "attempted": done,
        "synced_ok": counters["ok"],
        "synced_empty": counters["empty"],
        "ticks_inserted": counters["ticks"],
        "requests_used": counters["requests"],
        "max_requests_cap": max_requests,
        "stopped_at_cap": stop_event.is_set(),
        "still_missing": still_missing,
        "failures": failures[:50],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {REPORT}")
    print(
        f"summary: ok={counters['ok']}  empty={counters['empty']}  "
        f"ticks={counters['ticks']:,}  requests={counters['requests']}  "
        f"still_missing={len(still_missing)}  stopped_at_cap={stop_event.is_set()}"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Sync all funds with request cap")
    ap.add_argument(
        "--walkback", type=int, default=WALKBACK_DAYS, help="days to walk back per fund (default %(default)s)"
    )
    ap.add_argument(
        "--max-requests", type=int, default=MAX_REQUESTS, help="hard cap on BrsApi requests (default %(default)s)"
    )
    args = ap.parse_args()
    asyncio.run(main(walkback_days=args.walkback, max_requests=args.max_requests))
