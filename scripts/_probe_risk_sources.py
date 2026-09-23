"""Read-only: what real data can a risk page be computed from?

Answered 2026-09-22: ``portfolios`` and ``portfolio_positions`` hold **zero rows**, so
``/api/v1/risk`` has nothing to measure — which is why it now declares the gap instead of
showing the eight invented metrics it used to return. Price history is plentiful
(``brsapi_historical_daily`` ≈ 2.2k symbols; it carries a real ``gregorian_date`` column even
though the ORM model only declares the Jalali ``date`` string), and ``brsapi_index_values``
can serve as the beta benchmark once positions exist.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

QUERIES = [
    ("portfolios", "SELECT count(*) FROM portfolios"),
    ("positions", "SELECT count(*), count(DISTINCT portfolio_id), count(DISTINCT symbol) FROM portfolio_positions"),
    ("position sample", "SELECT portfolio_id, symbol, quantity, avg_cost, current_price, market_value, weight_pct FROM portfolio_positions ORDER BY market_value DESC NULLS LAST LIMIT 8"),
    ("index history tables", """SELECT table_name FROM information_schema.tables WHERE table_schema='public'
        AND (table_name ILIKE '%index%' OR table_name ILIKE '%daily_history%' OR table_name ILIKE '%brsapi_historical%') ORDER BY 1"""),
    ("daily_history coverage", "SELECT count(DISTINCT symbol_id), count(*), min(trade_date), max(trade_date) FROM daily_history"),
    ("brsapi hist coverage", "SELECT count(DISTINCT symbol), min(date), max(date) FROM brsapi_historical_daily"),
    ("alerts tables", """SELECT table_name FROM information_schema.tables WHERE table_schema='public'
        AND table_name ILIKE '%alert%' ORDER BY 1"""),
    ("watchlist/trades as holdings", "SELECT count(*) FROM trades"),
]


async def main() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    async with engine.connect() as conn:
        for label, sql in QUERIES:
            print("---", label)
            try:
                for row in (await conn.execute(text(sql))).fetchall()[:14]:
                    print("   ", row)
            except Exception as exc:
                print("    ERROR", type(exc).__name__, str(exc)[:150])
    await engine.dispose()


asyncio.run(main())
