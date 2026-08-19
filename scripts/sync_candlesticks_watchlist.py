"""
Candlestick backfill for the top N symbols (all three API types).

Syncs ``/Tsetmc/Candlestick.php`` for the most-traded symbols:

  - type=3 adjusted daily   (chart default)
  - type=2 unadjusted daily
  - type=1 realtime 2-min   (refreshed per poll — see sync_candlesticks)

Rate limit for the Candlestick endpoint is 2 req / 10s (12/min), so the
script waits 11s between requests (~5.5 req/min) — the API returns
``no_data``/empty bodies when hammered back-to-back.

Usage:
    python scripts/sync_candlesticks_watchlist.py --symbols 10
    python scripts/sync_candlesticks_watchlist.py --symbols فولاد,فملی,شپنا
"""
from __future__ import annotations

import argparse
import asyncio
import io
import sys
import time
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

if sys.platform == "win32":
    # Windows cp1252 console can't print Persian symbols — force UTF-8.
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

RATE_DELAY = 11.0  # seconds between requests (Candlestick: 2 req / 10s)


async def get_top_symbols(session, limit: int) -> list[str]:
    """Top symbols by trade value from the latest snapshot cycle."""
    from sqlalchemy import func, select

    from brsapi.models import SymbolSnapshotModel

    latest = select(func.max(SymbolSnapshotModel.fetched_at)).scalar_subquery()
    stmt = (
        select(SymbolSnapshotModel.symbol)
        .where(SymbolSnapshotModel.fetched_at == latest)
        .order_by(SymbolSnapshotModel.trade_value.desc().nullslast())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(dict.fromkeys(r[0] for r in result if r[0]))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill candlesticks for top symbols")
    parser.add_argument("--symbols", default="10", help="Top N count, or comma-separated symbol list")
    args = parser.parse_args()

    requested = args.symbols
    explicit = [s.strip() for s in requested.split(",") if s.strip() and not s.strip().isdigit()]
    count = int(requested) if requested.isdigit() else (len(explicit) or 10)

    import core.database as db
    from brsapi.client import get_client
    from brsapi.services.sync_service import BrsApiSyncService

    await db.init_database()
    client = await get_client()
    svc = BrsApiSyncService(client=client)

    async with db.async_session_factory() as session:
        if explicit:
            symbols = explicit
        else:
            symbols = await get_top_symbols(session, count)
        print(f"=== Candlestick backfill for {len(symbols)} symbols (types 3,2,1) ===", flush=True)
        if not symbols:
            print("  ! No symbols found — aborting", flush=True)
            return

        ok = fail = 0
        for i, sym in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}] {sym}", flush=True)
            for candle_type in ("3", "2", "1"):
                try:
                    report = await svc.sync_candlesticks(session, sym, candle_type=candle_type)
                    if report.success:
                        ok += 1
                        print(f"    type={candle_type}: {report.items_count} rows ({report.duration_ms:.0f}ms)", flush=True)
                    else:
                        fail += 1
                        print(f"    type={candle_type}: FAIL {(report.error or '')[:80]}", flush=True)
                except Exception as exc:  # noqa: BLE001
                    fail += 1
                    print(f"    type={candle_type}: EXC {str(exc)[:80]}", flush=True)
                await asyncio.sleep(RATE_DELAY)
            try:
                await session.commit()
            except Exception:
                await session.rollback()

        print(f"\n=== Done: {ok} ok, {fail} fail ===", flush=True)


if __name__ == "__main__":
    start = time.monotonic()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    print(f"Elapsed: {(time.monotonic() - start) / 60:.1f} minutes", flush=True)
