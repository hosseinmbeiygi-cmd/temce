"""Test script to debug real_legal table insertion."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# Force UTF-8
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from brsapi.models.tsetmc import HistoricalRealLegalModel
from core.database import close_database, get_session, init_database


async def main():
    base = r"C:\Users\Iran\Desktop\temce\real_legal_history_json"
    files = sorted([f for f in os.listdir(base) if f.endswith(".json")])
    print(f"FILES: {len(files)}")

    if not files:
        return

    path = os.path.join(base, files[0])
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    print(f"RECORDS: {len(data)}")

    if len(data) == 0:
        return

    rec = data[0]
    print(f"KEYS: {list(rec.keys())}")

    mapped = {
        "symbol": "test_sym",
        "date": rec["date"],
        "buy_legal_count": int(rec.get("Buy_CountI", 0) or 0),
        "buy_real_count": int(rec.get("Buy_CountN", 0) or 0),
        "sell_legal_count": int(rec.get("Sell_CountI", 0) or 0),
        "sell_real_count": int(rec.get("Sell_CountN", 0) or 0),
        "buy_legal_volume": int(rec.get("Buy_I_Volume", 0) or 0),
        "buy_real_volume": int(rec.get("Buy_N_Volume", 0) or 0),
        "sell_legal_volume": int(rec.get("Sell_I_Volume", 0) or 0),
        "sell_real_volume": int(rec.get("Sell_N_Volume", 0) or 0),
        "buy_legal_value": float(rec.get("Buy_I_Value", 0) or 0),
        "buy_real_value": float(rec.get("Buy_N_Value", 0) or 0),
        "sell_legal_value": float(rec.get("Sell_I_Value", 0) or 0),
        "sell_real_value": float(rec.get("Sell_N_Value", 0) or 0),
    }

    print("MAPPED: OK")

    await init_database()

    async for session in get_session():
        try:
            stmt = pg_insert(HistoricalRealLegalModel).values([mapped]).on_conflict_do_nothing()
            await session.execute(stmt)
            await session.commit()
            print("INSERT: OK")
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {str(e)[:200]}")

        r = await session.execute(text("SELECT COUNT(*) FROM brsapi_historical_real_legal"))
        print(f"COUNT: {r.scalar()}")
        break

    await close_database()


if __name__ == "__main__":
    asyncio.run(main())

