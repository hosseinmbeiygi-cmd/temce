"""FX History Backfill Script — fetches daily OHLC history for currency symbols.

Uses the BrsApi Gold_Currency_Pro endpoint (history=2) to backfill
daily price history for tracked FX symbols.

Usage:
    python scripts/fx_history_backfill.py                    # Backfill all FX symbols
    python scripts/fx_history_backfill.py --symbols USD EUR  # Backfill specific symbols
    python scripts/fx_history_backfill.py --dry-run          # Preview without writing
    python scripts/fx_history_backfill.py --start-date 1404-01-01  # Custom start date

Architecture:
    - Uses the existing BrsApiSyncService.sync_gold_currency_pro_daily_history()
    - Respects API rate limits with polite delays between requests
    - Provides progress tracking and error reporting
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.logging import get_logger

logger = get_logger(__name__)

# ── FX Symbols to Backfill ────────────────────────────────────────────

# Primary FX symbols for signal generation (free market rates)
FX_PRIMARY_SYMBOLS = [
    "USD",  # دلار — بازار آزاد
    "EUR",  # یورو
    "GBP",  # پوند
    "AED",  # درهم امارات
    "SAR",  # ریال عربستان
    "TRY",  # لیر ترکیه
    "USDT_IRT",  # دلار تتر
]

# Secondary FX symbols (additional currencies)
FX_SECONDARY_SYMBOLS = [
    "CNY",  # یوآن چین
    "JPY",  # ین ژاپن
    "CHF",  # فرانک سوئیس
    "CAD",  # دلار کانادا
    "AUD",  # دلار استرالیا
    "KWD",  # دینار کویت
]

# Gold symbol (for reference)
GOLD_SYMBOLS = [
    "XAUUSD",  # انس طلا
]

# All symbols to backfill
ALL_FX_SYMBOLS = FX_PRIMARY_SYMBOLS + FX_SECONDARY_SYMBOLS


# ── Backfill Configuration ────────────────────────────────────────────

# Default start date (Shamsi) — 1 year ago from today
DEFAULT_START_DATE = "1404-01-01"

# Delay between API requests (seconds) — respect rate limits
API_DELAY_SECONDS = 0.5

# Maximum symbols per run (to avoid quota exhaustion)
MAX_SYMBOLS_PER_RUN = 20


async def backfill_fx_history(
    symbols: list[str] | None = None,
    start_date: str = DEFAULT_START_DATE,
    end_date: str | None = None,
    dry_run: bool = False,
    include_gold: bool = False,
) -> dict:
    """Backfill daily OHLC history for FX symbols.

    Args:
        symbols: List of symbols to backfill. If None, uses ALL_FX_SYMBOLS.
        start_date: Shamsi start date (YYYY-MM-DD). Default: 1404-01-01.
        end_date: Shamsi end date (YYYY-MM-DD). Default: today.
        dry_run: If True, fetch but don't write to DB.
        include_gold: If True, also include XAUUSD.

    Returns:
        Dict with results: {symbol: {success, items_count, duration_ms, error}}
    """
    import core.database as db
    from brsapi.client import get_client
    from brsapi.services.sync_service import BrsApiSyncService

    # Initialize database
    await db.init_database()
    if db.async_session_factory is None:
        logger.error("Database not initialized")
        return {}

    # Determine symbols to backfill
    target_symbols = list(symbols) if symbols else list(ALL_FX_SYMBOLS)
    if include_gold:
        target_symbols.extend(GOLD_SYMBOLS)

    # Limit to MAX_SYMBOLS_PER_RUN
    if len(target_symbols) > MAX_SYMBOLS_PER_RUN:
        logger.warning(
            "Limiting to %d symbols (requested %d)",
            MAX_SYMBOLS_PER_RUN,
            len(target_symbols),
        )
        target_symbols = target_symbols[:MAX_SYMBOLS_PER_RUN]

    logger.info(
        "Starting FX history backfill: %d symbols, start=%s, end=%s, dry_run=%s",
        len(target_symbols),
        start_date,
        end_date or "today",
        dry_run,
    )

    # Initialize client and service
    client = await get_client()
    service = BrsApiSyncService(client=client)

    results: dict[str, dict] = {}
    total_items = 0
    total_errors = 0
    start_time = time.monotonic()

    async with db.async_session_factory() as session:
        for i, symbol in enumerate(target_symbols, 1):
            symbol_start = time.monotonic()
            logger.info(
                "[%d/%d] Backfilling %s...",
                i,
                len(target_symbols),
                symbol,
            )

            try:
                if dry_run:
                    # Just fetch and count, don't write
                    from brsapi.config import BrsApiEndpoints
                    from brsapi.parsers import GoldCurrencyProParser

                    params = {"history": "2", "symbol": symbol}
                    if start_date:
                        params["date_start"] = start_date
                    if end_date:
                        params["date_end"] = end_date

                    result = await client.fetch(BrsApiEndpoints.GOLD_CURRENCY_PRO, params=params)
                    if result.success:
                        data = result.value.data
                        parsed = GoldCurrencyProParser.parse_daily_history(data)
                        items_count = len(parsed) if parsed else 0
                        success = True
                        error = None
                    else:
                        items_count = 0
                        success = False
                        error = result.error
                else:
                    # Use the sync service to fetch and store
                    report = await service.sync_gold_currency_pro_daily_history(
                        session,
                        symbol=symbol,
                        date_start=start_date,
                        date_end=end_date,
                    )
                    items_count = report.items_count
                    success = report.success
                    error = report.error

                duration_ms = (time.monotonic() - symbol_start) * 1000
                results[symbol] = {
                    "success": success,
                    "items_count": items_count,
                    "duration_ms": duration_ms,
                    "error": error,
                }

                if success:
                    total_items += items_count
                    logger.info(
                        "  [OK] %s: %d items in %.0fms",
                        symbol,
                        items_count,
                        duration_ms,
                    )
                else:
                    total_errors += 1
                    logger.warning(
                        "  [FAIL] %s: failed — %s",
                        symbol,
                        error,
                    )

            except Exception as exc:
                duration_ms = (time.monotonic() - symbol_start) * 1000
                results[symbol] = {
                    "success": False,
                    "items_count": 0,
                    "duration_ms": duration_ms,
                    "error": str(exc),
                }
                total_errors += 1
                logger.exception("  [FAIL] %s: exception — %s", symbol, exc)

            # Polite delay between requests
            if i < len(target_symbols):
                await asyncio.sleep(API_DELAY_SECONDS)

        # Commit if not dry run
        if not dry_run:
            try:
                await session.commit()
                logger.info("[OK] All changes committed")
            except Exception as exc:
                await session.rollback()
                logger.error("[FAIL] Commit failed: %s", exc)
                total_errors = len(target_symbols)

    total_duration = (time.monotonic() - start_time) * 1000

    # Summary
    logger.info("=" * 60)
    logger.info("FX History Backfill Complete")
    logger.info("=" * 60)
    logger.info("Symbols processed: %d", len(target_symbols))
    logger.info("Total items fetched: %d", total_items)
    logger.info("Errors: %d", total_errors)
    logger.info("Total duration: %.1fs", total_duration / 1000)
    logger.info("=" * 60)

    # Per-symbol summary
    for symbol, result in results.items():
        status = "[OK]" if result["success"] else "[FAIL]"
        logger.info(
            "  %s %s: %d items (%.0fms)%s",
            status,
            symbol,
            result["items_count"],
            result["duration_ms"],
            f" — {result['error']}" if result["error"] else "",
        )

    return results


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill daily OHLC history for FX symbols from BrsApi",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Specific symbols to backfill (default: all FX symbols)",
    )
    parser.add_argument(
        "--start-date",
        default=DEFAULT_START_DATE,
        help=f"Shamsi start date (default: {DEFAULT_START_DATE})",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Shamsi end date (default: today)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch data but don't write to database",
    )
    parser.add_argument(
        "--include-gold",
        action="store_true",
        help="Also backfill XAUUSD (gold) history",
    )

    args = parser.parse_args()

    # Run the backfill
    asyncio.run(
        backfill_fx_history(
            symbols=args.symbols,
            start_date=args.start_date,
            end_date=args.end_date,
            dry_run=args.dry_run,
            include_gold=args.include_gold,
        )
    )


if __name__ == "__main__":
    main()
