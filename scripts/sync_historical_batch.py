"""
Bulk sync historical daily data from BrsApi for specified symbols.

Usage:
    python scripts/sync_historical_batch.py

Outputs a summary report showing which symbols succeeded and failed.
"""

# --- auto PYTHONPATH ---
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import sys
import time

# Fix Windows console encoding for Persian characters
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from brsapi.client import get_client
from brsapi.services.sync_service import BrsApiSyncService

# ── Top well-known TSE symbols (most traded) ──────────────
SYMBOLS = [
    "شپنا",      # 1. Palayesh Naft Esfahan
    "فملی",      # 2. National Copper (has data)
    "وبملت",     # 3. Bank Mellat (has data)
    "فولاد",     # 4. Foolad Mobarakeh
    "خودرو",     # 5. Iran Khodro
    "کگل",       # 6. Gol Gohar
    "شتران",     # 7. Palayesh Naft Tehran
    "شبندر",     # 8. Palayesh Naft Bandarabbas
    "شستا",      # 9. Shasta
    "تاپیکو",    # 10. Tapico
    "وغدیر",     # 11. Ghadir Investment
    "پترول",     # 12. Persian Gulf Petrochemical
    "وبصادر",    # 13. Bank Saderat
    "خساپا",     # 14. Saipa
    "رمپنا",     # 15. Mapna Group
]

# Add delay between requests to respect rate limits (30 req/min for TSETMC)
REQUEST_DELAY_SECONDS = 2.5


def safe_print(text: str) -> None:
    """Print with safe encoding fallback."""
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        # Strip non-ASCII chars for printing
        safe = text.encode("ascii", errors="replace").decode("ascii")
        print(safe, flush=True)


async def main():
    safe_print("=" * 60)
    safe_print("BrsApi Historical Data Sync")
    safe_print("=" * 60)
    safe_print(f"Symbols to sync: {len(SYMBOLS)}")
    safe_print(f"Delay between requests: {REQUEST_DELAY_SECONDS}s")
    safe_print("")

    # Connect to DB
    engine = create_async_engine(
        "postgresql+asyncpg://hossein:1343@localhost:5432/my_first_db",
        pool_size=5,
        max_overflow=10,
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Get BrsApi client
    try:
        client = await get_client()
        safe_print("[OK] BrsApi client connected")
    except Exception as exc:
        safe_print(f"[FAIL] BrsApi client error: {exc}")
        sys.exit(1)

    service = BrsApiSyncService(client=client)

    results = []
    total_start = time.monotonic()

    async with async_session() as session:
        for i, symbol in enumerate(SYMBOLS, 1):
            safe_print(f"[{i}/{len(SYMBOLS)}] Processing #{i}...")
            start = time.monotonic()

            try:
                report = await service.sync_history_price(session, symbol=symbol)
                elapsed = time.monotonic() - start
                results.append((symbol, report.success, report.items_count, elapsed))

                if report.success:
                    safe_print(f"  OK - {report.items_count} records in {elapsed:.1f}s")
                else:
                    safe_print(f"  FAIL - {report.error or 'unknown error'} ({elapsed:.1f}s)")

            except Exception as exc:
                elapsed = time.monotonic() - start
                results.append((symbol, False, 0, elapsed))
                safe_print(f"  ERROR - {exc} ({elapsed:.1f}s)")

            # Commit after each symbol
            try:
                await session.commit()
            except Exception:
                await session.rollback()

            # Respect rate limit
            if i < len(SYMBOLS):
                await asyncio.sleep(REQUEST_DELAY_SECONDS)

    total_elapsed = time.monotonic() - total_start

    # Summary
    safe_print("")
    safe_print("=" * 60)
    safe_print("SUMMARY")
    safe_print("=" * 60)
    success_count = sum(1 for _, s, _, _ in results if s)
    fail_count = len(results) - success_count
    total_records = sum(c for _, _, c, _ in results)

    safe_print(f"Total time: {total_elapsed:.1f}s")
    safe_print(f"Successful: {success_count}/{len(results)}")
    safe_print(f"Failed: {fail_count}/{len(results)}")
    safe_print(f"Total records inserted: {total_records}")
    safe_print("")

    safe_print("Per-symbol results:")
    for idx, (symbol, success, count, elapsed) in enumerate(results, 1):
        status = "OK" if success else "FAIL"
        # Use index-based output to avoid Persian char issues
        safe_print(f"  #{idx}: {status} - {count} records ({elapsed:.1f}s)")

    await engine.dispose()
    safe_print("")
    safe_print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
