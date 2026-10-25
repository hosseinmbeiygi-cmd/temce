"""DB probe (فقط SELECT) — شواهد برای گزارش طلا/نقره/صندوق‌ها.

هیچ INSERT/UPDATE/DELETE اجرا نمی‌شود؛ فقط خواندن.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from core import database  # noqa: E402

Q = {
    "gold_hist_symbols": """
        SELECT symbol, COUNT(*) AS n, MIN(date) AS d_min, MAX(date) AS d_max
        FROM brsapi_gold_coin_history GROUP BY symbol ORDER BY n DESC LIMIT 40
    """,
    "gold_hist_latest": """
        SELECT symbol, date, price_close FROM brsapi_gold_coin_history
        ORDER BY id DESC LIMIT 8
    """,
    "gold_hist_hardstop_symbols": """
        SELECT symbol, COUNT(*) FROM brsapi_gold_coin_history
        WHERE symbol IN ('USD','DXY','TSE_INDEX','INDEX','TEDPIX','XAUUSD','AED')
        GROUP BY symbol
    """,
    "real_legal_latest": """
        SELECT symbol, date, buy_real_value, sell_real_value FROM brsapi_historical_real_legal
        ORDER BY id DESC LIMIT 6
    """,
    "real_legal_symbols": """
        SELECT COUNT(DISTINCT symbol) FROM brsapi_historical_real_legal
    """,
    "fund_nav_history": """
        SELECT fund_id, COUNT(*), MIN(nav_date), MAX(nav_date) FROM fund_nav_history
        GROUP BY fund_id ORDER BY COUNT(*) DESC LIMIT 10
    """,
}


async def main() -> None:
    await database.init_database()
    factory = database.async_session_factory
    if factory is None:
        print("no db factory")
        return
    async with factory() as s:
        for name, sql in Q.items():
            print("=" * 70)
            print(name)
            print("=" * 70)
            try:
                rows = (await s.execute(text(sql))).all()
                if not rows:
                    print("  (no rows)")
                for r in rows[:40]:
                    print("  ", tuple(r))
            except Exception as exc:
                print(f"  ERROR: {type(exc).__name__}: {str(exc)[:160]}")

        print("=" * 70)
        print("tables of interest")
        print("=" * 70)
        t = (
            await s.execute(
                text(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema='public'
                      AND (table_name LIKE 'fund%' OR table_name LIKE '%gold%'
                           OR table_name LIKE '%brsapi_symbol_snapshot%')
                    ORDER BY table_name
                    """
                )
            )
        ).all()
        for (n,) in t:
            print("  ", n)


asyncio.run(main())
