#!/usr/bin/env python
"""
Import futures_history.json, symbols_high_trades.json, symbols_high_liquidity.json
into the database.

Usage:
    python scripts/import_analysis_data.py            # import all
    python scripts/import_analysis_data.py --dry-run  # preview only
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from sqlalchemy import text

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.database import close_database, get_session, init_database


async def ensure_tables() -> None:
    """Create tables for futures, high-trade symbols, and high-liquidity symbols."""
    async for session in get_session():
        # Futures contracts snapshot
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS futures_contracts (
                id SERIAL PRIMARY KEY,
                snapshot_time VARCHAR(30),
                contract_code VARCHAR(20) NOT NULL,
                contract_description TEXT,
                contract_size DOUBLE PRECISION,
                contract_size_unit VARCHAR(20),
                contract_currency VARCHAR(20),
                date_end VARCHAR(20),
                day_remain INTEGER,
                margin_initial DOUBLE PRECISION,
                margin_maintenance DOUBLE PRECISION,
                py DOUBLE PRECISION,
                pf DOUBLE PRECISION,
                pf_change DOUBLE PRECISION,
                pf_change_pct DOUBLE PRECISION,
                pmax DOUBLE PRECISION,
                pmax_change DOUBLE PRECISION,
                pmax_change_pct DOUBLE PRECISION,
                pmin DOUBLE PRECISION,
                pmin_change DOUBLE PRECISION,
                pmin_change_pct DOUBLE PRECISION,
                pl DOUBLE PRECISION,
                pl_change DOUBLE PRECISION,
                pl_change_pct DOUBLE PRECISION,
                trade_count INTEGER,
                trade_volume DOUBLE PRECISION,
                trade_value DOUBLE PRECISION,
                buy_real_count INTEGER,
                buy_legal_count INTEGER,
                sell_real_count INTEGER,
                sell_legal_count INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_futures_code ON futures_contracts(contract_code)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_futures_snapshot ON futures_contracts(snapshot_time)
        """))

        # High-trade symbols
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS symbols_high_trades (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(50) NOT NULL,
                total_days INTEGER,
                avg_trades DOUBLE PRECISION,
                max_trades DOUBLE PRECISION,
                min_trades DOUBLE PRECISION,
                days_above_threshold INTEGER,
                percent_above DOUBLE PRECISION,
                meets_criteria BOOLEAN DEFAULT TRUE,
                imported_at TIMESTAMP DEFAULT NOW()
            )
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_sht_symbol ON symbols_high_trades(symbol)
        """))

        # High-liquidity symbols
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS symbols_high_liquidity (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(50) NOT NULL,
                total_days INTEGER,
                avg_trades DOUBLE PRECISION,
                avg_volume DOUBLE PRECISION,
                avg_value DOUBLE PRECISION,
                max_trades DOUBLE PRECISION,
                max_volume DOUBLE PRECISION,
                max_value DOUBLE PRECISION,
                pct_trades DOUBLE PRECISION,
                pct_volume DOUBLE PRECISION,
                pct_value DOUBLE PRECISION,
                days_trades INTEGER,
                days_volume INTEGER,
                days_value INTEGER,
                criteria_met INTEGER,
                liquidity_score DOUBLE PRECISION,
                meets_criteria BOOLEAN DEFAULT TRUE,
                imported_at TIMESTAMP DEFAULT NOW()
            )
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_shl_symbol ON symbols_high_liquidity(symbol)
        """))

        await session.commit()
        break


async def import_futures(dry_run: bool) -> int:
    """Import futures_history.json."""
    fp = Path("futures_history.json")
    if not fp.exists():
        print("  futures_history.json not found")
        return 0

    with open(fp, encoding="utf-8") as f:
        snapshots = json.load(f)

    total = 0
    for snap in snapshots:
        snap_time = snap.get("timestamp", "")
        contracts = snap.get("data", [])

        if dry_run:
            print(f"  Futures snapshot {snap_time}: {len(contracts)} contracts")
            total += len(contracts)
            continue

        async for session in get_session():
            for c in contracts:
                await session.execute(text("""
                    INSERT INTO futures_contracts (
                        snapshot_time, contract_code, contract_description,
                        contract_size, contract_size_unit, contract_currency,
                        date_end, day_remain, margin_initial, margin_maintenance,
                        py, pf, pf_change, pf_change_pct,
                        pmax, pmax_change, pmax_change_pct,
                        pmin, pmin_change, pmin_change_pct,
                        pl, pl_change, pl_change_pct,
                        trade_count, trade_volume, trade_value,
                        buy_real_count, buy_legal_count, sell_real_count, sell_legal_count
                    ) VALUES (
                        :snapshot_time, :contract_code, :contract_description,
                        :contract_size, :contract_size_unit, :contract_currency,
                        :date_end, :day_remain, :margin_initial, :margin_maintenance,
                        :py, :pf, :pf_change, :pf_change_pct,
                        :pmax, :pmax_change, :pmax_change_pct,
                        :pmin, :pmin_change, :pmin_change_pct,
                        :pl, :pl_change, :pl_change_pct,
                        :trade_count, :trade_volume, :trade_value,
                        :buy_real_count, :buy_legal_count, :sell_real_count, :sell_legal_count
                    )
                """), {
                    "snapshot_time": snap_time,
                    "contract_code": c.get("contract_code", ""),
                    "contract_description": c.get("contract_description", ""),
                    "contract_size": c.get("contract_size"),
                    "contract_size_unit": c.get("contract_size_unit", ""),
                    "contract_currency": c.get("contract_currency", ""),
                    "date_end": c.get("date_end", ""),
                    "day_remain": c.get("day_remain"),
                    "margin_initial": c.get("margin_initial"),
                    "margin_maintenance": c.get("margin_maintenance"),
                    "py": c.get("py"),
                    "pf": c.get("pf"),
                    "pf_change": c.get("pfc"),
                    "pf_change_pct": c.get("pfp"),
                    "pmax": c.get("pmax"),
                    "pmax_change": c.get("pmaxc"),
                    "pmax_change_pct": c.get("pmaxp"),
                    "pmin": c.get("pmin"),
                    "pmin_change": c.get("pminc"),
                    "pmin_change_pct": c.get("pminp"),
                    "pl": c.get("pl"),
                    "pl_change": c.get("plc"),
                    "pl_change_pct": c.get("plp"),
                    "trade_count": c.get("tno"),
                    "trade_volume": c.get("tvol"),
                    "trade_value": c.get("tval"),
                    "buy_real_count": c.get("Buy_CountI"),
                    "buy_legal_count": c.get("Buy_CountN"),
                    "sell_real_count": c.get("Sell_CountI"),
                    "sell_legal_count": c.get("Sell_CountN"),
                })
            await session.commit()
            break

        total += len(contracts)
        print(f"  Futures snapshot {snap_time}: {len(contracts)} contracts OK")

    return total


async def import_high_trades(dry_run: bool) -> int:
    """Import symbols_high_trades.json."""
    fp = Path("symbols_high_trades.json")
    if not fp.exists():
        print("  symbols_high_trades.json not found")
        return 0

    with open(fp, encoding="utf-8") as f:
        data = json.load(f)

    symbols = data.get("symbols", [])
    criteria = data.get("criteria", {})

    if dry_run:
        print(f"  High-trade symbols: {len(symbols)} (criteria: {criteria})")
        return len(symbols)

    async for session in get_session():
        # Clear old data
        await session.execute(text("DELETE FROM symbols_high_trades"))

        for s in symbols:
            await session.execute(text("""
                INSERT INTO symbols_high_trades (
                    symbol, total_days, avg_trades, max_trades, min_trades,
                    days_above_threshold, percent_above, meets_criteria
                ) VALUES (
                    :symbol, :total_days, :avg_trades, :max_trades, :min_trades,
                    :days_above_threshold, :percent_above, :meets_criteria
                )
            """), {
                "symbol": s.get("symbol", ""),
                "total_days": s.get("total_days"),
                "avg_trades": s.get("avg_tno"),
                "max_trades": s.get("max_tno"),
                "min_trades": s.get("min_tno"),
                "days_above_threshold": s.get("days_above_threshold"),
                "percent_above": s.get("percent_above"),
                "meets_criteria": s.get("meets_criteria", True),
            })
        await session.commit()
        break

    print(f"  High-trade symbols: {len(symbols)} OK")
    return len(symbols)


async def import_high_liquidity(dry_run: bool) -> int:
    """Import symbols_high_liquidity.json."""
    fp = Path("symbols_high_liquidity.json")
    if not fp.exists():
        print("  symbols_high_liquidity.json not found")
        return 0

    with open(fp, encoding="utf-8") as f:
        data = json.load(f)

    symbols = data.get("symbols", [])
    criteria = data.get("criteria", {})

    if dry_run:
        print(f"  High-liquidity symbols: {len(symbols)} (criteria: {criteria})")
        return len(symbols)

    async for session in get_session():
        await session.execute(text("DELETE FROM symbols_high_liquidity"))

        for s in symbols:
            await session.execute(text("""
                INSERT INTO symbols_high_liquidity (
                    symbol, total_days, avg_trades, avg_volume, avg_value,
                    max_trades, max_volume, max_value,
                    pct_trades, pct_volume, pct_value,
                    days_trades, days_volume, days_value,
                    criteria_met, liquidity_score, meets_criteria
                ) VALUES (
                    :symbol, :total_days, :avg_trades, :avg_volume, :avg_value,
                    :max_trades, :max_volume, :max_value,
                    :pct_trades, :pct_volume, :pct_value,
                    :days_trades, :days_volume, :days_value,
                    :criteria_met, :liquidity_score, :meets_criteria
                )
            """), {
                "symbol": s.get("symbol", ""),
                "total_days": s.get("total_days"),
                "avg_trades": s.get("avg_tno"),
                "avg_volume": s.get("avg_tvol"),
                "avg_value": s.get("avg_tval"),
                "max_trades": s.get("max_tno"),
                "max_volume": s.get("max_tvol"),
                "max_value": s.get("max_tval"),
                "pct_trades": s.get("percent_tno"),
                "pct_volume": s.get("percent_tvol"),
                "pct_value": s.get("percent_tval"),
                "days_trades": s.get("days_tno"),
                "days_volume": s.get("days_tvol"),
                "days_value": s.get("days_tval"),
                "criteria_met": s.get("criteria_met"),
                "liquidity_score": s.get("liquidity_score"),
                "meets_criteria": s.get("meets_criteria", True),
            })
        await session.commit()
        break

    print(f"  High-liquidity symbols: {len(symbols)} OK")
    return len(symbols)


async def _run(dry_run: bool):
    print("=" * 60)
    print("  Analysis Data Import")
    print("=" * 60)
    if dry_run:
        print("  Mode: DRY RUN (no data saved)")
    print()

    start = time.monotonic()

    if not dry_run:
        await init_database()
        await ensure_tables()

    try:
        print("1) Futures contracts:")
        f_count = await import_futures(dry_run)

        print("\n2) High-trade symbols:")
        ht_count = await import_high_trades(dry_run)

        print("\n3) High-liquidity symbols:")
        hl_count = await import_high_liquidity(dry_run)

        elapsed = time.monotonic() - start
        print()
        print("=" * 60)
        print(f"  Done in {elapsed:.1f}s")
        print(f"  Futures contracts:  {f_count}")
        print(f"  High-trade symbols: {ht_count}")
        print(f"  High-liquid symbols: {hl_count}")
        print("=" * 60)

    finally:
        if not dry_run:
            await close_database()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import analysis data")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()
    asyncio.run(_run(args.dry_run))


if __name__ == "__main__":
    main()
