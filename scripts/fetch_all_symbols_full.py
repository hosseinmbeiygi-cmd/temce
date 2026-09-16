#!/usr/bin/env python3
"""🚀 Fetch AllSymbols + Full Symbol Detail for the whole market.

Workflow:
  1. Print current state of the BrsApi tables (row counts + freshness).
  2. Fetch ``AllSymbols.php`` and refresh ``brsapi_symbol_snapshots`` (1 call).
  3. Load the live symbol list from the snapshots table.
  4. For every symbol fetch ``Symbol.php?l18=<symbol>`` and store the enriched
     detail in ``brsapi_symbol_details`` (rate-limit aware + resumable).
  5. Dump all symbol details to ``json/brsapi/symbol_details.json`` plus one
     file per symbol under ``json/brsapi/symbol_details/``.

Usage:
    python scripts/fetch_all_symbols_full.py                # everything
    python scripts/fetch_all_symbols_full.py --limit 50     # first 50 symbols
    python scripts/fetch_all_symbols_full.py --no-skip-synced   # re-fetch all
    python scripts/fetch_all_symbols_full.py --api-key YOUR_BRSAPI_API_KEY
    python scripts/fetch_all_symbols_full.py --dry-run      # state + plan only

Rate limits (BrsApi official):
    AllSymbols  2 req/100s   (one call here)
    Symbol      3 req/10s    → ~18 req/min → full market ≈ 30-40 min
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# ── Auto PYTHONPATH ──────────────────────────────────────────────────────
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from brsapi.client import BrsApiClient  # noqa: E402
from brsapi.services.sync_service import BrsApiSyncService  # noqa: E402
from core.config import settings  # noqa: E402

JSON_DIR = Path(_project_root) / "json" / "brsapi" / "symbol_details"


def _p(msg: str) -> None:
    """Windows-safe print."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def _make_session(db_url: str):
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
    )
    session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, session


async def _table_state(session: AsyncSession) -> None:
    """Print row counts + freshness for the main BrsApi tables."""
    _p("\n=== 📊 وضعیت جداول BrsApi ===")
    queries = {
        "brsapi_symbol_snapshots": "SELECT count(*), max(fetched_at) FROM brsapi_symbol_snapshots",
        "brsapi_symbol_details": (
            "SELECT count(*), max(updated_at) FROM brsapi_symbol_details"
        ),
        "instruments": "SELECT count(*) FROM instruments",
    }
    for table, q in queries.items():
        try:
            row = (await session.execute(text(q))).fetchone()
            if row is None:
                _p(f"  {table:<28s} rows=0   latest=(empty table)")
                continue
            latest = row[1] if len(row) > 1 else "—"
            _p(f"  {table:<28s} rows={row[0]:>10,}   latest={latest}")
        except Exception as e:  # noqa: BLE001
            _p(f"  {table:<28s} ERR: {str(e)[:70]}")

    with contextlib.suppress(Exception):
        r = await session.execute(text(
            "SELECT count(DISTINCT symbol) FROM brsapi_symbol_snapshots"
        ))
        _p(f"  distinct snapshot symbols      = {r.scalar()}")
    with contextlib.suppress(Exception):
        r = await session.execute(text(
            "SELECT count(DISTINCT symbol) FROM brsapi_symbol_details"
        ))
        _p(f"  distinct detail symbols        = {r.scalar()}")


async def _fetch_all_symbols(client: BrsApiClient, session: AsyncSession) -> list[str]:
    """Fetch AllSymbols.php, refresh snapshots, return live symbol list."""
    _p("\n=== 🔄 دریافت AllSymbols.php ===")
    svc = BrsApiSyncService(client=client, session=session)
    report = await svc.sync_all_symbols(session)
    _p(
        f"  AllSymbols: success={report.success} items={report.items_count} "
        f"ms={report.duration_ms:.0f}"
    )
    await session.commit()

    r = await session.execute(text(
        "SELECT DISTINCT symbol FROM brsapi_symbol_snapshots "
        "WHERE symbol IS NOT NULL AND symbol != '' ORDER BY symbol"
    ))
    symbols = [row[0] for row in r.fetchall()]
    _p(f"  نمادهای زنده در snapshots: {len(symbols)}")
    return symbols


async def _already_synced(session: AsyncSession) -> set[str]:
    try:
        r = await session.execute(text(
            "SELECT DISTINCT symbol FROM brsapi_symbol_details "
            "WHERE symbol IS NOT NULL AND symbol != ''"
        ))
        return {row[0] for row in r.fetchall()}
    except Exception:  # noqa: BLE001
        return set()


async def _sync_details(
    client: BrsApiClient,
    session: AsyncSession,
    symbols: list[str],
    *,
    limit: int | None,
    delay: float,
    skip_synced: bool,
) -> dict:
    """Fetch Symbol.php detail for each symbol and store in the DB."""
    synced = await _already_synced(session) if skip_synced else set()
    todo = [s for s in symbols if s not in synced]
    if limit:
        todo = todo[:limit]

    _p(f"\n=== 🔄 دریافت اطلاعات کامل ({len(todo)} نماد) ===")
    if skip_synced:
        _p(f"  قبلاً sync شده: {len(symbols) - len(todo)} — پرش شد")
    if not todo:
        _p("  ✅ همه نمادها قبلاً sync شده‌اند. (برای re-fetch از --no-skip-synced استفاده کنید)")
        return {"ok": 0, "fail": 0, "skipped": 0, "total": 0}

    est_min = len(todo) * delay / 60
    _p(f"  ⏱️  زمان تقریبی: ~{est_min:.0f} دقیقه (delay={delay}s)")

    svc = BrsApiSyncService(client=client, session=session)
    ok = fail = skipped = 0
    errors: list[dict] = []
    start = time.monotonic()

    for idx, symbol in enumerate(todo, 1):
        t0 = time.monotonic()
        try:
            report = await svc.sync_symbol_detail(session, symbol)
            if report.success:
                ok += 1
            elif report.skipped:
                skipped += 1
            else:
                fail += 1
                errors.append({"symbol": symbol, "error": (report.error or "")[:120]})
            ms = (time.monotonic() - t0) * 1000
            _p(f"  [{idx:>4}/{len(todo)}] {'✅' if report.success else ('⏭' if report.skipped else '❌')} {symbol:<14s} {ms:6.0f}ms")
        except Exception as e:  # noqa: BLE001
            fail += 1
            errors.append({"symbol": symbol, "error": str(e)[:120]})
            _p(f"  [{idx:>4}/{len(todo)}] ❌ {symbol:<14s} {str(e)[:60]}")

        if idx % 10 == 0:
            try:
                await session.commit()
            except Exception:  # noqa: BLE001
                await session.rollback()
        if idx < len(todo):
            await asyncio.sleep(delay)

    try:
        await session.commit()
    except Exception:  # noqa: BLE001
        await session.rollback()

    elapsed = time.monotonic() - start
    _p(f"\n  نتیجه: ✅ {ok} | ⏭ {skipped} | ❌ {fail} | ⏱️ {elapsed/60:.1f} دقیقه")
    return {"ok": ok, "fail": fail, "skipped": skipped, "total": len(todo), "errors": errors[:20]}


async def _dump_json(session: AsyncSession) -> int:
    """Dump all symbol details from the DB to JSON files."""
    _p("\n=== 💾 ذخیره JSON ===")
    JSON_DIR.mkdir(parents=True, exist_ok=True)

    r = await session.execute(text("""
        SELECT ins_id, symbol, name, name_en, isin, code_12, code_5, code_4,
               market, board, board_id, board_code, sector, sector_id,
               sub_sector, sub_sector_id, shares_count, shares_issued,
               base_volume, market_value, free_float_pct, eps, pe_ratio,
               group_pe_ratio, ps_ratio, price_lowest_allowed,
               price_highest_allowed, price_min_week, price_max_week,
               price_min_year, price_max_year, price_min, price_max,
               price_yesterday, price_first, price_last, price_last_change,
               price_last_change_pct, price_close, price_close_change,
               price_close_change_pct, trade_count, trade_volume,
               trade_volume_avg_month, trade_value, buy_real_count,
               buy_legal_count, sell_real_count, sell_legal_count,
               buy_real_volume, buy_legal_volume, sell_real_volume,
               sell_legal_volume, state, date, time, updated_at
        FROM brsapi_symbol_details
    """))
    cols = [c[0] for c in r.cursor.description]
    rows = r.fetchall()
    all_records: list[dict] = []
    for row in rows:
        rec = dict(zip(cols, row, strict=False))
        all_records.append(rec)
        sym = rec.get("symbol") or "unknown"
        safe = "".join(ch if ch not in '<>:"/\\|?*' else "_" for ch in sym)
        with contextlib.suppress(Exception):
            (JSON_DIR / f"{safe}.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )

    summary = {
        "generated_at": _now(),
        "count": len(all_records),
        "source": "https://Api.BrsApi.ir/Tsetmc/Symbol.php",
        "fields": cols,
        "records": all_records,
    }
    (JSON_DIR.parent / "symbol_details.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    _p(f"  💾 {len(all_records)} نماد → {JSON_DIR} + symbol_details.json")
    return len(all_records)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch AllSymbols + full Symbol.php detail for all symbols")
    parser.add_argument("--db-url", type=str, default=None, help="Database URL (default: settings)")
    parser.add_argument("--api-key", type=str, default=None, help="BrsApi API key (default: BRSAPI_API_KEY env)")
    parser.add_argument("--limit", type=int, default=None, help="Max symbols to sync (default: all)")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between Symbol.php calls (default 1.0)")
    parser.add_argument("--skip-synced", dest="skip_synced", action="store_true", default=True,
                        help="Skip symbols that already have details (default)")
    parser.add_argument("--no-skip-synced", dest="skip_synced", action="store_false",
                        help="Re-fetch every symbol even if already synced")
    parser.add_argument("--dry-run", action="store_true", help="Print state + plan, make no API calls")
    parser.add_argument("--no-all-symbols", action="store_true",
                        help="Skip the AllSymbols refresh (use symbols already in snapshots)")
    args = parser.parse_args()

    db_url = args.db_url or settings.database_url
    engine, session_factory = await _make_session(db_url)

    _p("=" * 64)
    _p("🚀 دریافت AllSymbols + اطلاعات کامل همه نمادها")
    _p(f"    زمان اجرا: {_now()}")
    _p("=" * 64)

    try:
        async with session_factory() as session:
            # 1. Table state
            await _table_state(session)

            if args.dry_run:
                _p("\n🔍 DRY RUN — فقط وضعیت، بدون فراخوانی API")
                return

            # 2. AllSymbols
            client = BrsApiClient(api_key=args.api_key)
            await client.start()
            try:
                symbols = []
                if not args.no_all_symbols:
                    symbols = await _fetch_all_symbols(client, session)
                else:
                    r = await session.execute(text(
                        "SELECT DISTINCT symbol FROM brsapi_symbol_snapshots "
                        "WHERE symbol IS NOT NULL AND symbol != '' ORDER BY symbol"
                    ))
                    symbols = [row[0] for row in r.fetchall()]
                    _p(f"\n  استفاده از لیست موجود snapshots: {len(symbols)} نماد")

                if not symbols:
                    _p("\n⚠️ هیچ نمادی پیدا نشد — ابتدا AllSymbols را sync کنید.")
                    return

                # 3. Full details
                stats = await _sync_details(
                    client, session, symbols,
                    limit=args.limit, delay=args.delay, skip_synced=args.skip_synced,
                )

                # 4. JSON dump (of whatever is in the table now)
                n = await _dump_json(session)
                _p(f"\n🎉 جمع‌بندی: sync ok={stats['ok']} fail={stats['fail']} | JSON={n} نماد")
            finally:
                await client.stop()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    # Windows console fix
    if sys.platform == "win32":
        import contextlib

        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
