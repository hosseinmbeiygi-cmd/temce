"""
Run BrsApi Sync
===============

Triggers the BrsApi sync pipeline for key sections:
1. all-symbols  → brsapi_symbol_snapshots  (realtime, all symbols)
2. candlestick  → brsapi_candlesticks      (adjusted OHLCV, per-symbol)
3. history-price → brsapi_historical_daily (daily OHLCV, per-symbol)
4. history-real-legal → brsapi_historical_real_legal (real/legal, per-symbol)

Usage:
    python scripts/run_brsapi_sync.py              # all-symbols only (fast)
    python scripts/run_brsapi_sync.py --full        # all-symbols + history
    python scripts/run_brsapi_sync.py --sections all-symbols,candlestick
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from logging import getLogger

# Ensure the project root is on sys.path for imports
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logger = getLogger("brsapi_sync")


def _p(msg: str) -> None:
    """Print helper that avoids UnicodeEncodeError on Windows."""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Fallback: strip non-ASCII
        safe = msg.encode("ascii", errors="replace").decode("ascii")
        print(safe)


async def run_sync(sections: list[str], max_symbols: int = 10) -> None:
    """Run BrsApi sync for the given section list."""
    from brsapi.client import BrsApiClient
    from brsapi.config import BrsApiEndpoints, BrsApiSettings
    from brsapi.models import (
        CandlestickModel,
        HistoricalDailyModel,
        HistoricalRealLegalModel,
        SymbolSnapshotModel,
    )
    from brsapi.parsers import TsetmcParser
    from brsapi.repositories import SyncLogRepository
    from brsapi.services.sync_service import BrsApiSyncService
    from core.database import get_session
    from core.logging import setup_logging

    setup_logging()

    # Force UTF-8 for stdout/stderr (Windows cp1252 workaround)
    if sys.stdout.encoding and sys.stdout.encoding.upper() != "UTF-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr.encoding and sys.stderr.encoding.upper() != "UTF-8":
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    settings = BrsApiSettings()
    _p(f"BrsApi: {settings.base_url} | API key: {'SET' if settings.api_key else 'MISSING'}")
    if not settings.api_key:
        _p("ERROR: BRSAPI_API_KEY not set. Create a .env file or set env variable.")
        sys.exit(1)

    # Start HTTP client
    client = BrsApiClient()
    await client.start()
    _p("BrsApi HTTP client started [OK]")

    # Section definitions
    SECTION_MAP: dict[str, dict] = {
        "all-symbols": {
            "endpoint": BrsApiEndpoints.ALL_SYMBOLS,
            "model": SymbolSnapshotModel,
            "parser": TsetmcParser.parse_all_symbols,
            "truncate_first": True,
            "dedup_seconds": 30,
            "desc": "All symbols snapshot (single call)",
        },
        "candlestick": {
            "endpoint": BrsApiEndpoints.CANDLESTICK,
            "model": CandlestickModel,
            "parser": TsetmcParser.parse_candlesticks,
            "truncate_first": False,
            "dedup_seconds": 60,
            "desc": "Adjusted candlestick data (per-symbol)",
        },
        "history-price": {
            "endpoint": BrsApiEndpoints.HISTORY_PRICE,
            "model": HistoricalDailyModel,
            "parser": TsetmcParser.parse_history_price,
            "truncate_first": False,
            "dedup_seconds": 3600,
            "desc": "Daily OHLCV history (per-symbol)",
        },
        "history-real-legal": {
            "endpoint": BrsApiEndpoints.HISTORY_REALLEGAL,
            "model": HistoricalRealLegalModel,
            "parser": TsetmcParser.parse_history_real_legal,
            "truncate_first": False,
            "dedup_seconds": 3600,
            "desc": "Daily real/legal breakdown (per-symbol)",
        },
    }

    async for session in get_session():
        sync_svc = BrsApiSyncService(client=client, session=session)
        SyncLogRepository(session)

        for section_id in sections:
            cfg = SECTION_MAP.get(section_id)
            if not cfg:
                _p(f"  [?] Unknown section: {section_id}")
                continue

            _p(f"\n{'='*60}")
            _p(f"  [SYNC] {cfg['desc']}")
            _p(f"  [ENDPOINT] {cfg['endpoint'].path}")
            _p(f"{'='*60}")

            if section_id == "all-symbols":
                # Single API call — all symbols at once
                t0 = time.monotonic()
                report = await sync_svc.sync_all_symbols(session)
                elapsed = (time.monotonic() - t0) * 1000
                status = "OK" if report.success else "FAIL"
                _p(f"  [{status}] Done: {report.items_count} records in {elapsed:.0f}ms")
                if report.error:
                    _p(f"  [ERROR] {report.error}")

            else:
                # Per-symbol — fetch symbols list first
                from sqlalchemy import select

                stmt = select(SymbolSnapshotModel.symbol).order_by(SymbolSnapshotModel.symbol)
                result = await session.execute(stmt)
                symbols = [row[0] for row in result if row[0]]
                symbols = symbols[:max_symbols]
                _p(f"  [INFO] Syncing for {len(symbols)} symbols...")

                ok = fail = total_rows = 0
                for i, sym in enumerate(symbols):
                    # Use convenience methods that properly attach symbol + ins_id
                    if section_id == "candlestick":
                        report = await sync_svc.sync_candlesticks(session, sym, candle_type="3")
                    elif section_id == "history-price":
                        report = await sync_svc.sync_history_price(session, sym)
                    elif section_id == "history-real-legal":
                        report = await sync_svc.sync_history_real_legal(session, sym)
                    else:
                        # Fallback: raw sync (no symbol attachment)
                        report = await sync_svc.sync(
                            endpoint=cfg["endpoint"],
                            parser=cfg["parser"],
                            model_class=cfg["model"],
                            params={"l18": sym},
                            category_override="tsetmc",
                            session=session,
                        )

                    if report.success:
                        ok += 1
                        total_rows += report.items_count
                    else:
                        fail += 1

                    if report.items_count > 0:
                        _p(f"    [{i+1}/{len(symbols)}] {sym}: {report.items_count} rows ({report.duration_ms:.0f}ms)")
                    else:
                        _p(f"    [{i+1}/{len(symbols)}] {sym}: skipped ({report.duration_ms:.0f}ms)")

                    if report.error:
                        _p(f"    [WARN] {report.error}")

                    # Rate limit: ~30 req/min for TSETMC
                    if i < len(symbols) - 1:
                        await asyncio.sleep(2)

                _p(f"  [DONE] Result: {ok} ok, {fail} fail, {total_rows} total rows")

        # Commit all changes
        await session.commit()
        break  # single session use

    await client.stop()
    _p("\n[OK] BrsApi sync complete!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run BrsApi sync")
    parser.add_argument(
        "--sections",
        default="all-symbols",
        help="Comma-separated sections: all-symbols,candlestick,history-price,history-real-legal",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Sync all sections (all-symbols + history)",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=600,
        help="Max symbols for per-symbol sections (default: 600, 0=all)",
    )

    args = parser.parse_args()

    sections = args.sections.split(",")
    if args.full:
        sections = ["all-symbols", "candlestick", "history-price", "history-real-legal"]

    asyncio.run(run_sync(sections, max_symbols=args.max_symbols))
