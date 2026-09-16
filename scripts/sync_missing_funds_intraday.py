"""
Sync intraday trades for the 26 top-50 funds that currently have 0 ticks
in ``brsapi_intraday_trades``.

Strategy:
  - For each such fund, sync the most recent available Jalali trade_date
    (yesterday or the most recent session the API returns). We try
    yesterday first; if that yields 0 records, retry with a known-good
    recent date (the latest date in the table).
  - Run concurrently with a small semaphore to avoid hammering BrsApi.

After sync, rerun the top-50 selection and write the JSON again.
"""

import asyncio
from datetime import timedelta
from pathlib import Path

import jdatetime
from sqlalchemy import text

from brsapi.services.sync_service import BrsApiSyncService
from core import database
from core.time import now_tehran

OUT = Path("data") / "top50_funds_intraday.json"
TOP_N = 50
CONCURRENCY = 4


def _yesterday_jalali() -> str:
    today_g = now_tehran().date()
    yesterday_g = today_g - timedelta(days=1)
    j = jdatetime.date.fromgregorian(date=yesterday_g)
    return f"{j.year:04d}-{j.month:02d}-{j.day:02d}"


def _today_jalali() -> str:
    j = jdatetime.date.today()
    return f"{j.year:04d}-{j.month:02d}-{j.day:02d}"


async def _load_top50_symbols(s) -> tuple[list[tuple], list[str]]:
    """Same selection logic as the fetch script. Returns (rows, symbols)."""
    from brsapi.constants import BRSAPI_ETF_SYMBOLS

    rank_sql = text("""
        WITH latest AS (
            SELECT DISTINCT ON (symbol) symbol, name, sector, market_value, trade_volume
            FROM brsapi_symbol_snapshots
            WHERE market_value > 0
            ORDER BY symbol, fetched_at DESC
        )
        SELECT symbol, name, sector, market_value, trade_volume
        FROM latest
        WHERE sector = :fund_sector
           OR symbol = ANY(:etf_syms)
        ORDER BY market_value DESC
        LIMIT :top_n
    """)
    rows = (
        await s.execute(
            rank_sql,
            {
                "fund_sector": "صندوق سرمایه‌گذاری قابل معامله",
                "etf_syms": list(BRSAPI_ETF_SYMBOLS),
                "top_n": TOP_N,
            },
        )
    ).all()
    return rows, [r[0] for r in rows]


async def _funds_with_no_ticks(s, symbols: list[str]) -> list[str]:
    if not symbols:
        return []
    res = await s.execute(
        text("""
            SELECT symbol FROM brsapi_intraday_trades
            WHERE symbol = ANY(:syms)
            GROUP BY symbol HAVING COUNT(*) > 0
        """),
        {"syms": symbols},
    )
    have = {row[0] for row in res.all()}
    return [sym for sym in symbols if sym not in have]


async def _sync_one(svc: BrsApiSyncService, s, symbol: str, date_jalali: str) -> tuple[str, int, str]:
    """Returns (symbol, items_count, error_msg)."""
    try:
        report = await svc.sync_transactions(s, symbol=symbol, date=date_jalali)
        return symbol, report.items_count, "" if report.success else (report.error or "unknown")
    except Exception as e:
        return symbol, 0, str(e)[:200]


async def main() -> None:
    await database.init_database()
    factory = database.async_session_factory
    yesterday = _yesterday_jalali()
    today = _today_jalali()
    print(f"yesterday jalali: {yesterday}  today: {today}")

    async with factory() as s:
        rows, symbols = await _load_top50_symbols(s)
        print(f"top {TOP_N} selected; head={symbols[:5]}")
        missing = await _funds_with_no_ticks(s, symbols)
        print(f"funds with 0 intraday ticks: {len(missing)}")
        for m in missing:
            print(f"  - {m}")
        if not missing:
            print("nothing to sync")
            return

    # Build a list of candidate Jalali dates walking back from today.
    # BrsApi rejects holidays/weekends; we try up to 10 most-recent days.
    def _jalali_dates_back(n: int) -> list[str]:
        out: list[str] = []
        g = now_tehran().date()
        for i in range(n):
            d = g - timedelta(days=i)
            j = jdatetime.date.fromgregorian(date=d)
            out.append(f"{j.year:04d}-{j.month:02d}-{j.day:02d}")
        return out

    candidate_dates = _jalali_dates_back(14)  # 2 weeks of candidate days
    print(f"candidate dates: {candidate_dates[:5]} ... ({len(candidate_dates)} total)")

    # ── Sync (each call gets its own session) ─────────────────────
    sem = asyncio.Semaphore(CONCURRENCY)
    results: list[tuple[str, int, str]] = []

    async def _run(sym: str) -> None:
        async with sem:
            total = 0
            last_err = ""
            async with factory() as s:
                svc = BrsApiSyncService(session=s)
                for d in candidate_dates:
                    r = await _sync_one(svc, s, sym, d)
                    total += r[1]
                    if r[1] > 0:
                        # Got data for this date; stop early.
                        if last_err:
                            break
                        # but try one more day in case there are more ticks
                        # (no — single-day endpoint, just return)
                        last_err = ""
                        break
                    if r[2]:
                        last_err = r[2][:120]
            results.append((sym, total, last_err))

    await asyncio.gather(*[_run(sym) for sym in missing])

    # ── Report ─────────────────────────────────────
    print("\n=== sync results ===")
    inserted = 0
    failed = 0
    for sym, n, err in sorted(results, key=lambda x: -x[1]):
        marker = "OK" if n > 0 and not err else ("SKIP" if n == 0 and not err else "ERR")
        if marker == "ERR":
            failed += 1
        else:
            inserted += n
        print(f"  [{marker}] {sym:12} ticks={n:>7} {err}")
    print(f"\ntotal ticks inserted: {inserted}, failed funds: {failed}")

    # ── Regenerate top-50 output ───────────────────
    print("\nregenerating top-50 JSON...")

    # The fetch script uses module-level vars; safest is to just re-run it
    # in the same process — but it also calls asyncio.run. So invoke as a
    # subprocess.
    import subprocess
    import sys

    subprocess.run(
        [sys.executable, "-u", "scripts/fetch_top50_funds_intraday.py"],
        check=True,
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
