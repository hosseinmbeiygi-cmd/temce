"""Backfill intraday trades (ریز معاملات) for the last 6 months, whole market.

Usage:
    python scripts/backfill_trades_6mo.py --max-requests 2500
    python scripts/backfill_trades_6mo.py --max-requests 2500 --months 6 --symbols ETF1,ETF2

Design (quota-safe):
- 1 request per (symbol x trading day); TRANSACTION limit is 2 req/10s -> ~6s pause.
- Skips (symbol, trade_date) pairs already in brsapi_intraday_trades
  (matches both Jalali and Gregorian spellings - history has mixed formats).
- Stops cleanly on budget exhaustion (BudgetBlockedError / daily cap) and on
  --max-requests; progress is derived from the DB itself, so every run resumes.
- Trading days from domain.calendar.TradingCalendar (Sat-Wed, minus holidays).
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, timedelta
from pathlib import Path

import jdatetime
from sqlalchemy import text

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROGRESS_FILE = Path("data/backfill_trades_progress.json")


def trading_days(months: int) -> list[date]:
    from domain.calendar.trading_calendar import TradingCalendar
    cal = TradingCalendar()
    end = date.today()
    start = end - timedelta(days=int(months * 30.44) + 5)
    return cal.get_trading_days_list(start, end)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-requests", type=int, default=2500)
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--symbols", type=str, default="")
    ap.add_argument("--pause", type=float, default=6.0)
    args = ap.parse_args()

    from core.database import init_database
    await init_database()
    from core.database import async_session_factory
    from brsapi.services.sync_service import BrsApiSyncService

    days = trading_days(args.months)
    print(f"TRADING DAYS ({args.months}mo): {len(days)} from {days[0]} to {days[-1]}", flush=True)

    async with async_session_factory() as s:
        if args.symbols:
            symbols = [x.strip() for x in args.symbols.split(",") if x.strip()]
        else:
            rows = (await s.execute(text("SELECT DISTINCT symbol FROM brsapi_symbol_snapshots"))).fetchall()
            symbols = sorted(r[0] for r in rows if r[0])
        print(f"SYMBOLS: {len(symbols)}", flush=True)

        existing = set((await s.execute(
            text("SELECT symbol, trade_date FROM brsapi_intraday_trades"))).fetchall())
        existing = {(a, str(b)) for a, b in existing}
        print(f"EXISTING PAIRS: {len(existing)}", flush=True)

        svc = BrsApiSyncService()
        done = skipped = failed = 0
        total_targets = 0
        stop_reason = "max-requests"
        for sym in symbols:
            for d in days:
                jd = jdatetime.date.fromgregorian(date=d)
                jalali = f"{jd.year:04d}-{jd.month:02d}-{jd.day:02d}"
                greg = d.isoformat()
                total_targets += 1
                if (sym, jalali) in existing or (sym, greg) in existing:
                    skipped += 1
                    continue
                if done >= args.max_requests:
                    stop_reason = "max-requests"
                    break
                try:
                    await svc.sync_transactions(s, sym, date=jalali)
                    done += 1
                except Exception as e:
                    msg = str(e).lower()
                    if any(k in msg for k in ("exhaust", "blocked", "cap", "quota", "429", "limit")):
                        stop_reason = f"budget: {str(e)[:100]}"
                        break
                    failed += 1
                    if failed <= 5:
                        print(f"  FAIL {sym} {jalali}: {str(e)[:120]}", flush=True)
                await asyncio.sleep(args.pause)
            if stop_reason.startswith("budget") or done >= args.max_requests:
                break

        PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROGRESS_FILE.write_text(json.dumps({
            "months": args.months, "symbols": len(symbols), "days": len(days),
            "targets": total_targets, "done": done, "skipped": skipped,
            "failed": failed, "stop": stop_reason,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"DONE={done} SKIPPED={skipped} FAILED={failed} STOP={stop_reason}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
