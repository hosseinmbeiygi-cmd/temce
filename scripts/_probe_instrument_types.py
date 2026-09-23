"""Read-only: which instrument classes can this database actually evidence?

Answers the question the pre-buy instrument axis depends on — for each class in
``core.question_bank.schema.InstrumentType``, is there a populated table that says a symbol
belongs to it, or would the claim be invented? Run it again before authoring a new module
(``tasks #16/#17``) or adding an ``InstrumentType`` value.

    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/_probe_instrument_types.py

Nothing is written; every statement is a SELECT.
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

#: (instrument type, question being answered, sql, what a "yes" needs)
CHECKS: list[tuple[str, str, str]] = [
    ("equity", "`instruments` by class",
     "SELECT market_type, asset_class, count(*) FROM instruments GROUP BY 1,2 ORDER BY 3 DESC"),
    ("etf / fund", "`symbols` non-stock rows, and how `funds` types them",
     """SELECT s.symbol, s.market_type, s.asset_class, f.fund_type
        FROM symbols s LEFT JOIN funds f ON lower(f.symbol) = lower(s.symbol)
        WHERE s.market_type <> 'stock' ORDER BY s.symbol"""),
    ("fund / leveraged_fund / fixed_income", "`funds.fund_type` domain and size",
     "SELECT fund_type, count(*) FROM funds GROUP BY 1 ORDER BY 2 DESC"),
    ("commodity_fund", "`brsapi_ime_funds` membership (the only gold/commodity-fund signal)",
     "SELECT count(DISTINCT symbol) AS symbols, count(*) AS rows FROM brsapi_ime_funds"),
    ("option", "option contract tables",
     "SELECT 'options' t, count(DISTINCT symbol) n FROM options "
     "UNION ALL SELECT 'commodity_options', count(DISTINCT symbol) FROM commodity_options "
     "UNION ALL SELECT 'brsapi_ime_options', count(DISTINCT call_contract_code) FROM brsapi_ime_options"),
    ("future", "futures contract tables",
     "SELECT 'commodity_futures' t, count(DISTINCT symbol) n FROM commodity_futures "
     "UNION ALL SELECT 'brsapi_ime_futures', count(DISTINCT contract_code) FROM brsapi_ime_futures"),
    ("commodity_certificate", "certificate tables",
     "SELECT 'commodity_certificates' t, count(DISTINCT symbol) n FROM commodity_certificates "
     "UNION ALL SELECT 'brsapi_ime_certificates', count(DISTINCT contract_code) FROM brsapi_ime_certificates"),
    ("GOLD FUND as its own class", "`gold_fund_nav` / `gold_snapshots` — both must have rows",
     "SELECT 'gold_fund_nav' t, count(*) n FROM gold_fund_nav "
     "UNION ALL SELECT 'gold_snapshots', count(*) FROM gold_snapshots"),
    ("fixed income (bonds) as an instrument", "any bond table at all (note: `paper_*` is the "
     "paper-trading feature, not اوراق — a hit here means nothing)",
     """SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' AND (table_name ILIKE '%bond%' OR table_name ILIKE '%paper%'
          OR table_name ILIKE '%fixed_income%' OR table_name ILIKE '%reit%' OR table_name ILIKE '%property%')
        ORDER BY 1"""),
]


async def main() -> int:
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            for label, question, sql in CHECKS:
                print(f"\n=== {label} — {question}")
                try:
                    rows = (await conn.execute(text(sql))).fetchall()
                except Exception as exc:
                    print(f"    ERROR {type(exc).__name__}: {str(exc)[:140]}")
                    continue
                if not rows:
                    print("    (no rows — this class cannot be evidenced from the database)")
                for row in rows[:24]:
                    print("   ", row)
                if len(rows) > 24:
                    print(f"    … {len(rows) - 24} more")
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
