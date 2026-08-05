"""
Per-symbol incremental sync for the top N symbols (by trade value).

Syncs the heavy "تاریخچه" tables plus per-symbol tables that the batch auto
sync does not cover:

  - History Price          → brsapi_historical_daily
  - History Real/Legal     → brsapi_historical_real_legal
  - Symbol Detail          → brsapi_symbol_details
  - Shareholder            → brsapi_shareholder_records
  - Candlestick            → brsapi_candlesticks

History/real-legal are incremental by nature: the API returns the full series
and the DB upsert (ON CONFLICT DO NOTHING) only inserts dates that are not
already stored, so we "update from the last" without re-processing gaps.

Usage:
    python scripts/sync_top_symbols_history.py --symbols 30 --delay 3.0
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
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


async def get_top_symbols(session, limit: int) -> list[str]:
    """Top symbols by trade value from the latest snapshots (same query as the auto sync)."""
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
    parser = argparse.ArgumentParser(description="Per-symbol history/detail sync for top symbols")
    parser.add_argument("--symbols", type=int, default=30, help="Top N symbols (default 30)")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds between requests (default 3)")
    args = parser.parse_args()

    import core.database as db
    from brsapi.client import get_client
    from brsapi.services.sync_service import BrsApiSyncService

    await db.init_database()
    client = await get_client()
    svc = BrsApiSyncService(client=client)

    ops = [
        ("History Price (تاریخچه)", lambda s: svc.sync_history_price(session, s)),
        ("History Real/Legal (حقیقی/حقوقی)", lambda s: svc.sync_history_real_legal(session, s)),
        ("Symbol Detail (جزئیات)", lambda s: svc.sync_symbol_detail(session, s)),
        ("Shareholder (سهامداران)", lambda s: svc.sync_shareholders(session, s)),
        ("Candlestick (شمعی)", lambda s: svc.sync_candlesticks(session, s)),
    ]

    async with db.async_session_factory() as session:
        symbols = await get_top_symbols(session, args.symbols)
        print(f"═══ Per-symbol sync for {len(symbols)} top symbols ═══", flush=True)
        if not symbols:
            print("  ⚠️ No symbols found — aborting", flush=True)
            return

        ok = fail = 0
        for i, sym in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}] {sym}", flush=True)
            for name, fn in ops:
                try:
                    r = await fn(sym)
                    if r.success:
                        ok += 1
                        print(f"    ✅ {name}: {r.items_count} records", flush=True)
                    else:
                        fail += 1
                        print(f"    ❌ {name}: {(r.error or '')[:70]}", flush=True)
                except Exception as e:  # noqa: BLE001
                    fail += 1
                    print(f"    ⚠️ {name}: {str(e)[:70]}", flush=True)
                await asyncio.sleep(args.delay)
            try:
                await session.commit()
            except Exception:
                await session.rollback()

        print(f"\n═══ Done: {ok} ok, {fail} fail ═══", flush=True)


if __name__ == "__main__":
    start = time.monotonic()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
    print(f"Elapsed: {(time.monotonic() - start) / 60:.1f} minutes", flush=True)
