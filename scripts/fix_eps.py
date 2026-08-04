"""
Fix EPS in screener_profiles
============================

Copies EPS, PE ratio, shares_count and other available fields from
brsapi_symbol_snapshots (or brsapi_symbol_details) into screener_profiles.

Usage:
    python scripts/fix_eps.py
"""

from __future__ import annotations

import os
import sys
import time

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.logging import setup_logging

setup_logging()


def _p(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        safe = msg.encode("ascii", errors="replace").decode("ascii")
        print(safe)


async def run() -> None:
    from sqlalchemy import text

    from core.database import get_session

    t0 = time.monotonic()

    async for session in get_session():
        # ── 1. Copy EPS from brsapi_symbol_snapshots ──
        _p("[STEP 1/4] Copying EPS from brsapi_symbol_snapshots...")
        r = await session.execute(text("""
            UPDATE screener_profiles sp
            SET eps_current = sub.eps,
                updated_at = NOW()
            FROM (
                SELECT DISTINCT ON (symbol) symbol, eps
                FROM brsapi_symbol_snapshots
                WHERE eps IS NOT NULL AND eps > 0
                ORDER BY symbol, created_at DESC
            ) sub
            WHERE sp.symbol = sub.symbol
        """))
        updated_eps = r.rowcount
        _p(f"  -> {updated_eps} profiles updated with EPS")

        # ── 2. Copy PE ratio ──
        _p("[STEP 2/4] Copying PE ratio from brsapi_symbol_details...")
        r = await session.execute(text("""
            UPDATE screener_profiles sp
            SET industry_pe = sub.group_pe_ratio,
                updated_at = NOW()
            FROM (
                SELECT DISTINCT ON (symbol) symbol, group_pe_ratio
                FROM brsapi_symbol_details
                WHERE group_pe_ratio IS NOT NULL AND group_pe_ratio > 0
                ORDER BY symbol, updated_at DESC
            ) sub
            WHERE sp.symbol = sub.symbol
        """))
        updated_pe = r.rowcount
        _p(f"  -> {updated_pe} profiles updated with group PE ratio")

        # ── 3. Copy shares_count and free_float_pct ──
        _p("[STEP 3/4] Copying shares_count and free_float from details...")
        r = await session.execute(text("""
            UPDATE screener_profiles sp
            SET free_float_shares = sub.free_float,
                registered_capital = sub.capital,
                updated_at = NOW()
            FROM (
                SELECT DISTINCT ON (symbol) symbol,
                    CAST(shares_count * COALESCE(free_float_pct, 0) / 100.0 AS BIGINT) AS free_float,
                    shares_count * 1000 / 1e9 AS capital
                FROM brsapi_symbol_details
                WHERE shares_count IS NOT NULL AND shares_count > 0
                ORDER BY symbol, updated_at DESC
            ) sub
            WHERE sp.symbol = sub.symbol
        """))
        updated_ff = r.rowcount
        _p(f"  -> {updated_ff} profiles updated with free_float / capital")

        # ── 4. Copy sector as industry (for symbols missing industry) ──
        _p("[STEP 4/4] Copying sector from snapshots as fallback industry...")
        r = await session.execute(text("""
            UPDATE screener_profiles sp
            SET industry = sub.sector,
                updated_at = NOW()
            FROM (
                SELECT DISTINCT ON (symbol) symbol, sector
                FROM brsapi_symbol_snapshots
                WHERE sector IS NOT NULL AND sector != ''
                ORDER BY symbol, created_at DESC
            ) sub
            WHERE sp.symbol = sub.symbol
              AND (sp.industry IS NULL OR sp.industry = '')
        """))
        updated_sector = r.rowcount
        _p(f"  -> {updated_sector} profiles updated with sector as industry")

        # Commit all changes
        await session.commit()
        elapsed = time.monotonic() - t0

        # ── 5. Show final coverage ──
        _p(f"\n{'='*60}")
        _p(f"[DONE] Fix complete in {elapsed:.2f}s")
        _p(f"{'='*60}")

        r = await session.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE eps_current IS NOT NULL AND eps_current > 0) as eps_filled,
                COUNT(*) FILTER (WHERE free_float_shares IS NOT NULL AND free_float_shares > 0) as ff_filled,
                COUNT(*) FILTER (WHERE registered_capital IS NOT NULL AND registered_capital > 0) as cap_filled,
                COUNT(*) FILTER (WHERE industry IS NOT NULL AND industry != '') as ind_filled,
                COUNT(*) FILTER (WHERE industry_pe IS NOT NULL AND industry_pe > 0) as pe_filled,
                COUNT(*) as total
            FROM screener_profiles
        """))
        row = dict(r.fetchone()._mapping)
        _p(f"\nFinal coverage (out of {row['total']}):")
        _p(f"  EPS:              {row['eps_filled']}")
        _p(f"  Free float:       {row['ff_filled']}")
        _p(f"  Capital:          {row['cap_filled']}")
        _p(f"  Industry:         {row['ind_filled']}")
        _p(f"  Industry PE:      {row['pe_filled']}")

        # Sample
        r = await session.execute(text("""
            SELECT symbol, eps_current, free_float_shares, registered_capital, industry_pe
            FROM screener_profiles
            WHERE eps_current > 0
            LIMIT 5
        """))
        _p("\nSample data (with EPS):")
        for row in r.fetchall():
            _p(f"  {dict(row._mapping)}")

        break


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
