#!/usr/bin/env python
"""Backfill ``daily_adjust_factors`` for every symbol that has corporate actions.

Idempotent — safe to re-run after importing new events. Usage:

    # all symbols with actions
    python scripts/backfill_adjust_factors.py

    # one symbol
    python scripts/backfill_adjust_factors.py --symbol وبانک
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg

from core.config import settings
from core.logging import get_logger
from services.corporate_action_service import compute_cumulative_factors

logger = get_logger("backfill_adjust_factors")


async def main(symbol_arg: str | None) -> None:
    dsn = str(settings.database_url).replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)

    try:
        if symbol_arg:
            rows = await conn.fetch("SELECT id FROM symbols WHERE symbol = $1", symbol_arg)
        else:
            rows = await conn.fetch("SELECT DISTINCT symbol_id FROM corporate_actions")
        logger.info("symbols to process: %d", len(rows))

        total = 0
        for r in rows:
            sid = int(r["id"] if "id" in r.keys() else r["symbol_id"])

            actions = await conn.fetch(
                "SELECT ex_date, action_type, ratio, dps FROM corporate_actions WHERE symbol_id=$1 ORDER BY ex_date",
                sid,
            )
            if not actions:
                continue

            trade_dates = [
                rec["trade_date"]
                for rec in await conn.fetch(
                    "SELECT trade_date FROM daily_history WHERE symbol_id=$1", sid
                )
            ]
            ex_dates = [a["ex_date"] for a in actions]
            close_rows = await conn.fetch(
                "SELECT trade_date, price_close FROM daily_history WHERE symbol_id=$1 AND trade_date = ANY($2::date[])",
                sid,
                ex_dates,
            )
            closes = {rec["trade_date"]: float(rec["price_close"]) for rec in close_rows}

            factors = compute_cumulative_factors(
                [dict(a) for a in actions], trade_dates, closes
            )

            await conn.executemany(
                """
                INSERT INTO daily_adjust_factors (symbol_id, trade_date, adj_factor, computed_at)
                VALUES ($1, $2, $3, now())
                ON CONFLICT (symbol_id, trade_date) DO UPDATE
                SET adj_factor = EXCLUDED.adj_factor, computed_at = now()
                """,
                [(sid, d, f) for d, f in factors.items()],
                timeout=60,
            )
            total += len(factors)
            logger.info("symbol %s: %d factor rows", sid, len(factors))

        logger.info("DONE — factors written: %d", total)
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill daily adjust factors")
    parser.add_argument("--symbol", default=None, help="single symbol ticker")
    args = parser.parse_args()
    asyncio.run(main(args.symbol))
