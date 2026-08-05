"""
Automatic BrsApi sync script — syncs ALL tables to the latest trading day.

Usage:
    python scripts/sync_all_tables_auto.py            # sync everything possible
    python scripts/sync_all_tables_auto.py --phase 3  # only intraday trades
    python scripts/sync_all_tables_auto.py --days 3   # transactions for last N days

How it works:
1. Detects whether the TSETMC daily quota is exhausted (HTTP 402).
2. Always syncs 24/7 endpoints (Gold, Currency, Crypto, Commodity) — free quota.
3. Syncs TSETMC endpoints (AllSymbols, Index, Transactions, Options, IME, Codal)
   only when quota allows; skips gracefully with a message when 402.
4. For intraday transactions (ریز معاملات) it passes **Jalali (Shamsi)** dates
   to the API (e.g. 1405-05-12), because BrsApi rejects Gregorian dates with 400.

Exit codes: 0 = ok (possibly skipped), 1 = fatal.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
from datetime import timedelta
from logging import getLogger

sys.path.insert(0, ".")

# Force UTF-8 stdout/stderr on Windows so emoji (✅❌⚠️) and Persian text
# don't crash the script with UnicodeEncodeError (cp1252 default).
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from core.logging import setup_logging  # noqa: E402

logger = getLogger(__name__)


async def _quota_allows(client) -> bool:
    """Quick probe: does the TSETMC quota still allow requests?"""
    from brsapi.client import get_client
    from brsapi.config import BrsApiEndpoints

    client = client or await get_client()
    res = await client.fetch(BrsApiEndpoints.INDEX, params={"type": "1"})
    return res.success


async def run(
    phase: int | None = None,
    days_back: int = 3,
    num_symbols: int = 30,
    skip_symbols: int = 0,
) -> None:
    import core.database as db
    from brsapi.client import get_client
    from brsapi.services.sync_service import BrsApiSyncService

    await db.init_database()
    client = await get_client()
    svc = BrsApiSyncService(client=client)

    async with db.async_session_factory() as session:
        # ── Phase 0: always-available endpoints (free daily quota) ──
        if phase is None or phase == 0:
            print("\n═══ PHASE 0: Gold / Currency / Crypto / Commodity (24/7) ═══")
            reports = await svc.sync_gold_currency(session)
            for r in reports:
                print(f"  {'✅' if r.success else '❌'} {r.endpoint:40s} items={r.items_count}")
            for name, fn in [
                ("Commodities", lambda: svc.sync_commodities(session)),
                ("Crypto", lambda: svc.sync_crypto(session)),
            ]:
                r = await fn()
                print(f"  {'✅' if r.success else '❌'} {name:40s} items={r.items_count} "
                      f"{(r.error or '')[:60]}")
            await session.commit()

        # ── Quota probe for TSETMC ──
        tsetmc_ok = await _quota_allows(client)
        print(f"\nTSETMC quota: {'✅ available' if tsetmc_ok else '❌ exhausted (HTTP 402)'}")

        # ── Phase 1: Bulk TSETMC (AllSymbols + Index) ──
        if (phase is None or phase == 1) and tsetmc_ok:
            print("\n═══ PHASE 1: TSETMC bulk (AllSymbols + Index) ═══")
            for name, fn in [
                ("AllSymbols", lambda: svc.sync_all_symbols(session)),
                ("Index (TSE)", lambda: svc.sync_index(session, "1")),
                ("Index (Farabourse)", lambda: svc.sync_index(session, "2")),
            ]:
                r = await fn()
                print(f"  {'✅' if r.success else '❌'} {name:20s} items={r.items_count} "
                      f"{(r.error or '')[:60]}")
            await asyncio.sleep(2)

        # ── Phase 2: Options + IME (separate quotas, try anyway) ──
        if (phase is None or phase == 2) and tsetmc_ok:
            print("\n═══ PHASE 2: Options + IME ═══")
            for name, fn in [
                ("TSETMC Options", lambda: svc.sync_options(session)),
                ("IME Futures", lambda: svc.sync_ime_futures(session)),
                ("IME Options", lambda: svc.sync_ime_options(session)),
                ("IME Certificates", lambda: svc.sync_ime_certificates(session)),
                ("IME Funds", lambda: svc.sync_ime_funds(session)),
            ]:
                r = await fn()
                print(f"  {'✅' if r.success else '❌'} {name:20s} items={r.items_count} "
                      f"{(r.error or '')[:60]}")
            await asyncio.sleep(2)

        # ── Phase 3: Intraday transactions (ریز معاملات) for top symbols ──
        if phase is None or phase == 3:
            print("\n═══ PHASE 3: Intraday Transactions (ریز معاملات) ═══")
            from sqlalchemy import func, select, text

            from brsapi.models import SymbolSnapshotModel

            latest = select(func.max(SymbolSnapshotModel.fetched_at)).scalar_subquery()
            stmt = (
                select(SymbolSnapshotModel.symbol)
                .where(SymbolSnapshotModel.fetched_at == latest)
                .order_by(SymbolSnapshotModel.trade_value.desc().nullslast())
                .limit(num_symbols)
            )
            result = await session.execute(stmt)
            symbols = list(dict.fromkeys(r[0] for r in result if r[0]))
            if skip_symbols:
                symbols = symbols[skip_symbols:]
                print(f"  Skipping first {skip_symbols}; continuing with {len(symbols)} symbols")
            else:
                print(f"  Top {len(symbols)} symbols (by trade value)")

            # Use REAL trading days instead of naive calendar-day subtraction:
            # the Tehran market is closed Thu/Fri, so naive timedelta would send
            # useless requests for holidays (and burn daily quota). Trading dates
            # are taken from the historical table, which only holds trading days.
            rows = (await session.execute(text(
                "SELECT DISTINCT date FROM brsapi_historical_daily "
                "ORDER BY date DESC LIMIT :n"
            ), {"n": days_back})).fetchall()
            dates = [row[0] for row in rows]
            if not dates:
                # Fallback: naive last N days if history table is empty
                import jdatetime

                dates = [
                    (jdatetime.date.today() - timedelta(days=d)).strftime("%Y-%m-%d")
                    for d in range(days_back)
                ]
            print(f"  Dates (Jalali trading days): {dates}")

            ok = fail = total = 0
            for sym in symbols:
                for date in dates:
                    try:
                        r = await svc.sync_transactions(session, sym, date)
                        if r.success:
                            ok += 1
                            total += r.items_count
                            if r.items_count:
                                print(f"    ✅ {sym:15s} {date}: {r.items_count} trades")
                        else:
                            fail += 1
                            err = (r.error or "").replace("\n", " ")[:50]
                            if "402" in (r.error or ""):
                                print(f"    ⏸️ {sym:15s} {date}: QUOTA EXHAUSTED — stopping phase")
                                print(f"\n  Phase 3 stopped: {ok} ok, {fail} fail, {total} trades synced")
                                await session.commit()
                                return
                            print(f"    ❌ {sym:15s} {date}: {err}")
                    except Exception as e:
                        fail += 1
                        print(f"    ⚠️ {sym:15s} {date}: {str(e)[:50]}")
                    await asyncio.sleep(5.5)  # rate limit 2 req / 10s
            print(f"\n  Phase 3 done: {ok} ok, {fail} fail, {total} trades synced")
            await session.commit()

        # ── Phase 5: Codal ──
        if (phase is None or phase == 5) and tsetmc_ok:
            print("\n═══ PHASE 5: Codal ═══")
            r = await svc.sync_codal(session)
            print(f"  {'✅' if r.success else '❌'} Codal items={r.items_count} {(r.error or '')[:60]}")
            await session.commit()


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Sync all BrsApi tables (auto quota-aware)")
    parser.add_argument("--phase", type=int, default=None, help="Run only this phase (0-5)")
    parser.add_argument("--days", type=int, default=3, help="Transactions: trading days back (default 3)")
    parser.add_argument("--symbols", type=int, default=30,
                        help="Intraday transactions: number of top symbols (default 30)")
    parser.add_argument("--skip", type=int, default=0,
                        help="Intraday transactions: skip first N top symbols (resume support)")
    args = parser.parse_args()

    try:
        asyncio.run(run(
            phase=args.phase,
            days_back=args.days,
            num_symbols=args.symbols,
            skip_symbols=args.skip,
        ))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as exc:  # noqa: BLE001
        logger.exception("Fatal error")
        print(f"\n❌ Fatal: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
