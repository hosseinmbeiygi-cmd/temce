"""
Analyze Shareholder Changes
============================

Analyzes the 769K shareholder records in brsapi_shareholder_records to find:
1. Symbols with the most shareholder changes in the last 30 days
2. Biggest net buyers (shareholders increasing positions)
3. Biggest % ownership changes
4. Busiest days

Usage:
    python scripts/analyze_shareholders.py
"""

from __future__ import annotations

import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import core.fix_network  # noqa: F401
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

    async for session in get_session():
        # Use a CTE to clean dates once: REPLACE hyphens and cast to int
        DATE_30 = """
            WITH _max_dt AS (
                SELECT MAX(REPLACE(date, '-', '')::int) - 30 AS cutoff
                FROM brsapi_shareholder_records
            )
        """
        DATE_FILTER = "REPLACE(brsapi_shareholder_records.date, '-', '')::int >= (SELECT cutoff FROM _max_dt)"

        # Date range
        r = await session.execute(
            text("SELECT MAX(date), MIN(date) FROM brsapi_shareholder_records")
        )
        row = r.fetchone()
        _p(f"📅 Data range: {row[1]} to {row[0]}")
        _p("")

        # ── 1. Most shareholder changes ────────────────────────
        _p("=" * 70)
        _p("📊 TOP 20 — MOST SHAREHOLDER CHANGES (last ~30d)")
        _p("=" * 70)
        r = await session.execute(
            text(f"""
                {DATE_30}
                SELECT symbol,
                       COUNT(*) as total,
                       SUM(CASE WHEN change = 1 THEN 1 ELSE 0 END) as inc,
                       SUM(CASE WHEN change = 2 THEN 1 ELSE 0 END) as dec,
                       SUM(CASE WHEN change = 3 THEN 1 ELSE 0 END) as new,
                       COUNT(DISTINCT shareholder_name) as holders
                FROM brsapi_shareholder_records, _max_dt
                WHERE {DATE_FILTER}
                  AND change IN (1, 2, 3)
                GROUP BY symbol
                ORDER BY total DESC
                LIMIT 20
            """)
        )
        header = f"  {'Symbol':>8s}  {'Total':>7s}  {'+Inc':>7s}  {'-Dec':>7s}  {'New':>5s}  {'Holders':>7s}"
        _p(header)
        _p("-" * len(header))
        for row in r.fetchall():
            _p(f"  {row[0]:>8s}  {row[1]:>7,}  {row[2]:>7,}  {row[3]:>7,}  {row[4]:>5,}  {row[5]:>7,}")

        # ── 2. Biggest net buyers ──────────────────────────────
        _p("")
        _p("=" * 90)
        _p("🏦 TOP 20 SHAREHOLDERS — BIGGEST NET BUYERS (last ~30d)")
        _p("=" * 90)
        r = await session.execute(
            text(f"""
                {DATE_30}
                SELECT shareholder_name,
                       COUNT(DISTINCT symbol) as symbols,
                       SUM(CASE WHEN change = 1 THEN volume ELSE 0 END) as bought,
                       SUM(CASE WHEN change = 2 THEN volume ELSE 0 END) as sold,
                       SUM(CASE WHEN change = 1 THEN volume ELSE 0 END)
                       - SUM(CASE WHEN change = 2 THEN volume ELSE 0 END) as net
                FROM brsapi_shareholder_records, _max_dt
                WHERE {DATE_FILTER}
                  AND change IN (1, 2)
                GROUP BY shareholder_name
                HAVING SUM(CASE WHEN change = 1 THEN volume ELSE 0 END) > 0
                ORDER BY net DESC
                LIMIT 20
            """)
        )
        _p(f"  {'Shareholder':40s}  {'Sym':>4s}  {'Bought':>14s}  {'Sold':>14s}  {'Net':>14s}")
        _p("-" * 88)
        for row in r.fetchall():
            _p(f"  {str(row[0])[:38]:40s}  {row[1]:>4,}  {row[2]:>14,}  {row[3]:>14,}  {row[4]:>+14,}")

        # ── 3. Highest ownership concentration ─────────────────
        _p("")
        _p("=" * 70)
        _p("🔄 TOP 15 — HIGHEST OWNERSHIP CONCENTRATION (last ~30d)")
        _p("=" * 70)
        r = await session.execute(
            text(f"""
                {DATE_30}
                , latest AS (
                    SELECT DISTINCT ON (symbol, shareholder_name)
                        symbol, shareholder_name, percent, date
                    FROM brsapi_shareholder_records, _max_dt
                    WHERE {DATE_FILTER}
                      AND percent > 0
                    ORDER BY symbol, shareholder_name, date DESC
                )
                SELECT symbol,
                       ROUND(CAST(MAX(percent) AS NUMERIC), 2) as max_pct,
                       ROUND(CAST(AVG(percent) AS NUMERIC), 2) as avg_pct,
                       COUNT(*) as holders,
                       ROUND(CAST(SUM(percent) AS NUMERIC), 2) as total_pct
                FROM latest
                GROUP BY symbol
                ORDER BY total_pct DESC
                LIMIT 15
            """)
        )
        _p(f"  {'Symbol':>8s}  {'Max%':>7s}  {'Avg%':>7s}  {'Holders':>7s}  {'Total%':>7s}")
        _p("-" * 45)
        for row in r.fetchall():
            _p(f"  {row[0]:>8s}  {row[1]:>7.2f}  {row[2]:>7.2f}  {row[3]:>7,}  {row[4]:>7.2f}")

        # ── 4. Busiest days ────────────────────────────────────
        _p("")
        _p("=" * 70)
        _p("📅 BUSIEST DAYS — most shareholder changes (last ~30d)")
        _p("=" * 70)
        r = await session.execute(
            text(f"""
                {DATE_30}
                SELECT date, COUNT(*) as changes
                FROM brsapi_shareholder_records, _max_dt
                WHERE {DATE_FILTER}
                GROUP BY date
                ORDER BY changes DESC
                LIMIT 10
            """)
        )
        _p(f"  {'Date':>12s}  {'Changes':>8s}")
        _p("-" * 22)
        for row in r.fetchall():
            _p(f"  {str(row[0]):>12s}  {row[1]:>8,}")

        # ── 5. Net volume change per symbol ────────────────────
        _p("")
        _p("=" * 90)
        _p("📈 TOP 20 SYMBOLS — NET VOLUME CHANGE (last ~30d)")
        _p("=" * 90)
        r = await session.execute(
            text(f"""
                {DATE_30}
                SELECT symbol,
                       SUM(CASE WHEN change = 1 THEN volume ELSE 0 END) as bought,
                       SUM(CASE WHEN change = 2 THEN volume ELSE 0 END) as sold,
                       SUM(CASE WHEN change = 1 THEN volume ELSE 0 END)
                       - SUM(CASE WHEN change = 2 THEN volume ELSE 0 END) as net_vol,
                       COUNT(DISTINCT shareholder_name) as holders_changed
                FROM brsapi_shareholder_records, _max_dt
                WHERE {DATE_FILTER}
                  AND change IN (1, 2)
                GROUP BY symbol
                HAVING SUM(CASE WHEN change = 1 THEN volume ELSE 0 END) > 0
                ORDER BY ABS(
                    SUM(CASE WHEN change = 1 THEN volume ELSE 0 END)
                    - SUM(CASE WHEN change = 2 THEN volume ELSE 0 END)
                ) DESC
                LIMIT 20
            """)
        )
        _p(f"  {'Symbol':>8s}  {'Bought':>14s}  {'Sold':>14s}  {'Net Change':>14s}  {'Holders':>8s}")
        _p("-" * 65)
        for row in r.fetchall():
            net = row[3] or 0
            arrow = "⬆️" if net > 0 else "⬇️"
            _p(f"  {row[0]:>8s}  {row[1]:>14,}  {row[2]:>14,}  {net:>+14,}  {row[4]:>8,}  {arrow}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
