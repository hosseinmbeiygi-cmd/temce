"""
Populate Screener Profiles
==========================

Reads existing DB data (symbols, daily_history, daily_real_legal,
symbol_snapshots, gold_currency_prices) and populates/updates
the screener_profiles table.

Usage:
    python scripts/populate_profiles.py
"""

from __future__ import annotations

import os
import sys
import time
from logging import getLogger

# Ensure the project root is on sys.path for imports
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logger = getLogger("populate_profiles")


def _p(msg: str) -> None:
    """Print helper that avoids UnicodeEncodeError on Windows."""
    try:
        print(msg)
    except UnicodeEncodeError:
        safe = msg.encode("ascii", errors="replace").decode("ascii")
        print(safe)


async def run() -> None:
    from core.database import get_session
    from core.logging import setup_logging
    from services.populate_profiles_service import PopulateProfilesService

    setup_logging()

    # Force UTF-8 for stdout/stderr
    if sys.stdout.encoding and sys.stdout.encoding.upper() != "UTF-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr.encoding and sys.stderr.encoding.upper() != "UTF-8":
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    _p("[INFO] Starting screener_profiles population...")
    t0 = time.monotonic()

    async for session in get_session():
        svc = PopulateProfilesService(session)
        summary = await svc.populate_all()

        await session.commit()
        elapsed = time.monotonic() - t0

        _p(f"\n[DONE] Population complete in {elapsed:.2f}s")
        _p(f"  Total symbols: {summary['total']}")
        _p(f"  Created:       {summary['created']}")
        _p(f"  Updated:       {summary['updated']}")
        _p(f"  Skipped:       {summary['skipped']}")
        break  # single session


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
