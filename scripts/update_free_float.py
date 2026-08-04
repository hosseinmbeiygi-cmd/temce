"""
Update Free Float from Shareholder Data
========================================

Estimates free_float_shares for screener_profiles using the shareholder
records in brsapi_shareholder_records.

Logic:
  - For each symbol, find the latest shareholder snapshot.
  - Sum the percentages of ALL recorded shareholders → known_pct.
  - The unrecorded portion is assumed to be retail / free float:
        free_float_pct ≈ 100% - known_pct
  - Convert to shares:
        free_float_shares = registered_capital × 1,000,000 × free_float_pct / 100

  This gives a much more accurate estimate than the current hardcoded 20%.

Usage:
    python scripts/update_free_float.py
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
        # ── Step 1: Calculate free_float_pct for each symbol ──
        _p("=" * 65)
        _p("📊 STEP 1: Calculating free_float from shareholder records")
        _p("=" * 65)

        r = await session.execute(text("""
            WITH latest_holders AS (
                -- Get the latest snapshot per (symbol, shareholder_name)
                SELECT DISTINCT ON (symbol, shareholder_name)
                    symbol, shareholder_name, percent
                FROM brsapi_shareholder_records
                WHERE percent IS NOT NULL AND percent > 0
                ORDER BY symbol, shareholder_name, date DESC
            ),
            symbol_total AS (
                -- Sum known percentages per symbol
                SELECT symbol,
                       ROUND(SUM(percent)::numeric, 2) as known_pct,
                       COUNT(*) as known_holders
                FROM latest_holders
                GROUP BY symbol
            )
            SELECT symbol, known_pct, known_holders,
                   GREATEST(0, 100.0 - known_pct) as free_float_pct
            FROM symbol_total
            ORDER BY symbol
        """))

        rows = r.fetchall()
        _p(f"  Symbols with shareholder data: {len(rows)}")
        _p("  Sample:")
        for row in rows[:5]:
            _p(f"    {row[0]:>8s}  known={row[1]:>7.2f}%  holders={row[2]:>4,}  ff_est={row[3]:>6.2f}%")

        # ── Step 2: Update screener_profiles ──────────────────
        _p("\n" + "=" * 65)
        _p("📥 STEP 2: Updating screener_profiles.free_float_shares")
        _p("=" * 65)

        r = await session.execute(text("""
            WITH ff_data AS (
                SELECT sh.symbol,
                       ROUND(SUM(sh.percent)::numeric, 2) as known_pct,
                       COUNT(*) as holders
                FROM (
                    SELECT DISTINCT ON (symbol, shareholder_name)
                        symbol, shareholder_name, percent
                    FROM brsapi_shareholder_records
                    WHERE percent IS NOT NULL AND percent > 0
                    ORDER BY symbol, shareholder_name, date DESC
                ) sh
                GROUP BY sh.symbol
            )
            UPDATE screener_profiles sp
            SET free_float_shares = CAST(
                    GREATEST(0, 100.0 - ff.known_pct)
                    * COALESCE(sp.registered_capital, 0) * 1000000.0 / 100.0
                AS BIGINT),
                updated_at = NOW()
            FROM ff_data ff
            WHERE sp.symbol = ff.symbol
              AND COALESCE(sp.registered_capital, 0) > 0
              AND GREATEST(0, 100.0 - ff.known_pct) BETWEEN 1 AND 99
        """))

        updated = r.rowcount
        _p(f"  Profiles updated with free_float: {updated}")

        # ── Step 3: Summary ──────────────────────────────────
        await session.commit()
        elapsed = time.monotonic() - t0

        _p("\n" + "=" * 65)
        _p("📋 SUMMARY")
        _p("=" * 65)

        r = await session.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE free_float_shares IS NOT NULL AND free_float_shares > 0) as filled,
                COUNT(*) FILTER (WHERE free_float_shares IS NULL OR free_float_shares = 0) as empty,
                ROUND(AVG(free_float_shares)::numeric, 0) as avg_ff,
                MAX(free_float_shares) as max_ff,
                MIN(free_float_shares) FILTER (WHERE free_float_shares > 0) as min_ff
            FROM screener_profiles
        """))
        row = r.fetchone()
        _p("  Before:  98 profiles had free_float")
        _p(f"  After:   {row[0]} profiles have free_float")
        _p(f"  Empty:   {row[1]}")
        _p(f"  Avg FF:  {row[2]:,.0f} shares")
        _p(f"  Max FF:  {row[3]:,}")
        _p(f"  Min FF:  {row[4]:,}")
        _p(f"  Time:    {elapsed:.1f}s")

        # Sample top 5 by free_float_pct
        _p("\n📈 Top 5 by free_float %:")
        r = await session.execute(text("""
            WITH ff_data AS (
                SELECT sh.symbol,
                       ROUND(SUM(sh.percent)::numeric, 2) as known_pct
                FROM (
                    SELECT DISTINCT ON (symbol, shareholder_name)
                        symbol, shareholder_name, percent
                    FROM brsapi_shareholder_records
                    WHERE percent IS NOT NULL AND percent > 0
                    ORDER BY symbol, shareholder_name, date DESC
                ) sh
                GROUP BY sh.symbol
            )
            SELECT sp.symbol,
                   ROUND(ff.known_pct::numeric, 2),
                   ROUND(GREATEST(0, 100.0 - ff.known_pct)::numeric, 2) as ff_pct,
                   sp.free_float_shares,
                   sp.registered_capital
            FROM screener_profiles sp
            JOIN ff_data ff ON sp.symbol = ff.symbol
            WHERE sp.free_float_shares IS NOT NULL AND sp.free_float_shares > 0
            ORDER BY ff_pct DESC
            LIMIT 5
        """))
        for row in r.fetchall():
            _p(f"  {row[0]:>8s}  known={row[1]:>7.2f}%  FF%={row[2]:>6.2f}%  shares={row[3]:>15,}  cap={row[4]:>8.1f}B")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
