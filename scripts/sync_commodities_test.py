"""
Quick test: sync global commodity prices from BrsApi -> PostgreSQL.

If a real BRSAPI_API_KEY is not provided or the API returns 401,
the test falls back to mock data so the full pipeline
(parser -> DB insert -> query verification) can be verified.

Usage:
    # With a real API key:
    BRSAPI_API_KEY=YourKey python scripts/sync_commodities_test.py

    # With mock data (no API key needed):
    python scripts/sync_commodities_test.py
"""

from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.database import close_database, get_session, init_database


# ── Mock commodity data ────────────────────────────────────────────

MOCK_COMMODITY_DATA = {
    "XAUUSD": {"symbol": "XAUUSD", "name": "Gold", "price": 2335.67, "change_value": 12.45, "change_percent": 0.54, "unit": "USD", "time": "16:30", "date": "1404/04/07"},
    "XAGUSD": {"symbol": "XAGUSD", "name": "Silver", "price": 29.58, "change_value": -0.32, "change_percent": -1.07, "unit": "USD", "time": "16:30", "date": "1404/04/07"},
    "XPTUSD": {"symbol": "XPTUSD", "name": "Platinum", "price": 987.50, "change_value": 5.20, "change_percent": 0.53, "unit": "USD", "time": "16:30", "date": "1404/04/07"},
    "XPDUSD": {"symbol": "XPDUSD", "name": "Palladium", "price": 956.00, "change_value": -8.75, "change_percent": -0.91, "unit": "USD", "time": "16:30", "date": "1404/04/07"},
    "COPPER": {"symbol": "COPPER", "name": "Copper", "price": 4.52, "change_value": 0.03, "change_percent": 0.67, "unit": "USD", "time": "16:25", "date": "1404/04/07"},
    "ALUMINUM": {"symbol": "ALUMINUM", "name": "Aluminum", "price": 2498.00, "change_value": 15.00, "change_percent": 0.60, "unit": "USD", "time": "16:25", "date": "1404/04/07"},
    "ZINC": {"symbol": "ZINC", "name": "Zinc", "price": 2867.00, "change_value": -12.00, "change_percent": -0.42, "unit": "USD", "time": "16:25", "date": "1404/04/07"},
    "LEAD": {"symbol": "LEAD", "name": "Lead", "price": 2160.00, "change_value": 8.50, "change_percent": 0.39, "unit": "USD", "time": "16:25", "date": "1404/04/07"},
    "NICKEL": {"symbol": "NICKEL", "name": "Nickel", "price": 19120.00, "change_value": -150.00, "change_percent": -0.78, "unit": "USD", "time": "16:25", "date": "1404/04/07"},
    "BRENT": {"symbol": "BRENT", "name": "Brent Crude", "price": 86.73, "change_value": 1.15, "change_percent": 1.34, "unit": "USD", "time": "17:00", "date": "1404/04/07"},
    "WTI": {"symbol": "WTI", "name": "WTI Crude", "price": 82.91, "change_value": 0.98, "change_percent": 1.19, "unit": "USD", "time": "17:00", "date": "1404/04/07"},
    "NGAS": {"symbol": "NGAS", "name": "Natural Gas", "price": 2.47, "change_value": -0.04, "change_percent": -1.59, "unit": "USD", "time": "17:00", "date": "1404/04/07"},
}


async def main() -> int:
    # 1. Init DB
    print("=" * 55)
    print("  STEP 1: Initialize database")
    print("=" * 55)
    await init_database()
    print("  [OK] Database connected")

    # 2. Attempt real API sync, fallback to mock
    print(f"\n{'='*55}")
    print("  STEP 2: Fetch commodity data")
    print("=" * 55)

    from brsapi.models import CommodityPriceModel
    from brsapi.parsers.commodity import CommodityParser
    from brsapi.repositories.base import BulkUpsertRepository, SyncLogRepository
    from sqlalchemy import func as sa_func, select

    records = []
    used_mock = False

    api_key = os.environ.get("BRSAPI_API_KEY", "")
    if api_key:
        print(f"  Using real API (key present)...")
        try:
            from brsapi.client import get_client, close_client
            from brsapi.config import BrsApiEndpoints

            client = await get_client()
            result = await client.fetch(BrsApiEndpoints.COMMODITY)

            if result.success and result.value and not result.value.is_empty:
                print(f"  [OK] API returned data")
                parsed = CommodityParser.parse(result.value.data)
                records = parsed if isinstance(parsed, list) else [parsed] if parsed else []
                print(f"  Parsed {len(records)} records from API")
            else:
                err = result.error or "empty response"
                print(f"  API returned: {err}")
                print(f"  Falling back to mock data...")
                used_mock = True
            await close_client()
        except Exception as e:
            print(f"  API error: {e}")
            print(f"  Falling back to mock data...")
            used_mock = True
    else:
        print(f"  No BRSAPI_API_KEY set. Using mock data.")
        used_mock = True

    if used_mock:
        # fetched_at is varchar(30) in the DB — use a short ISO format
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        for symbol, info in MOCK_COMMODITY_DATA.items():
            from brsapi.parsers.commodity import CommodityParser as CP
            rec = {
                "symbol": symbol,
                "name": info.get("name", ""),
                "price": CP._float(info.get("price", 0)),
                "change_value": CP._float(info.get("change_value", 0)),
                "change_percent": CP._float(info.get("change_percent", 0)),
                "unit": info.get("unit", "USD"),
                "category": CP.classify(symbol),
                "date": info.get("date", ""),
                "time": info.get("time", ""),
                "fetched_at": now,
                "raw_json": json.dumps(info, ensure_ascii=False),
            }
            records.append(rec)
        print(f"  Generated {len(records)} mock records")

    # 3. Store in database
    print(f"\n{'='*55}")
    print("  STEP 3: Store in PostgreSQL")
    print("=" * 55)

    async for session in get_session():
        # Truncate previous test data so we start clean
        repo = BulkUpsertRepository(session, CommodityPriceModel)
        await repo.truncate()

        # Insert in batches
        BATCH_SIZE = 500
        total = 0
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i : i + BATCH_SIZE]
            inserted = await repo.bulk_insert(batch)
            total += inserted
        await session.commit()

        print(f"  Inserted {total} records")

        # Log sync — naive datetimes to match DB column type
        from brsapi.models.base import SyncLogModel
        from datetime import datetime as dt_naive

        session.add(SyncLogModel(
            endpoint="/Market/Commodity.php",
            category="commodity",
            status="success",
            items_count=total,
            started_at=dt_naive.now(),
            completed_at=dt_naive.now(),
        ))
        await session.flush()
        break  # Only one iteration needed

    # 4. Verify in database
    print(f"\n{'='*55}")
    print("  STEP 4: Verify data in PostgreSQL")
    print("=" * 55)

    async for session in get_session():
        # Total count
        cnt = await session.execute(select(sa_func.count()).select_from(CommodityPriceModel))
        db_total = cnt.scalar() or 0
        print(f"  Total rows in brsapi_commodity_prices: {db_total}")

        # By category
        cat_result = await session.execute(
            select(CommodityPriceModel.category, sa_func.count().label("cnt"))
            .group_by(CommodityPriceModel.category)
            .order_by(CommodityPriceModel.category)
        )
        print("\n  Category breakdown:")
        for row in cat_result:
            label = {
                "precious_metal": "Precious Metals",
                "base_metal": "Base Metals",
                "energy": "Energy",
            }.get(row.category or "", row.category or "other")
            print(f"    {label:20s} -> {row.cnt} items")

        # Sample records
        sample = await session.execute(
            select(CommodityPriceModel)
            .order_by(CommodityPriceModel.change_percent.desc().nullslast())
            .limit(len(records))
        )
        rows = sample.scalars().all()

        print(f"\n  All commodities ({len(rows)} total):")
        print(f"  {'Symbol':10s} {'Name':25s} {'Price':>10s} {'Change%':>8s} {'Category':20s}")
        print(f"  {'-'*10} {'-'*25} {'-'*10} {'-'*8} {'-'*20}")
        for r in rows:
            sign = "+" if (r.change_percent or 0) >= 0 else ""
            cat_label = {
                "precious_metal": "Precious Metal",
                "base_metal": "Base Metal",
                "energy": "Energy",
            }.get(r.category or "", r.category or "other")
            print(f"  {r.symbol:10s} {r.name or '':25s} ${r.price:>8.2f} {sign}{r.change_percent or 0:>+6.2f}% {cat_label:20s}")

        # Verify categories are correct
        gold = next((r for r in rows if r.symbol == "XAUUSD"), None)
        copper = next((r for r in rows if r.symbol == "COPPER"), None)
        brent = next((r for r in rows if r.symbol == "BRENT"), None)

        print(f"\n  Category classification check:")
        print(f"    XAUUSD (Gold)     -> {gold.category if gold else 'N/A'}  (expected: precious_metal)")
        print(f"    COPPER (Copper)   -> {copper.category if copper else 'N/A'}  (expected: base_metal)")
        print(f"    BRENT (Brent Oil) -> {brent.category if brent else 'N/A'}  (expected: energy)")

        all_ok = all([
            gold and gold.category == "precious_metal",
            copper and copper.category == "base_metal",
            brent and brent.category == "energy",
        ])

        # Price formatting check
        print(f"\n  Price format check:")
        if gold:
            print(f"    Gold    = ${gold.price:,.2f}  (raw: {gold.price})")
        if silver := next((r for r in rows if r.symbol == "XAGUSD"), None):
            print(f"    Silver  = ${silver.price:,.2f}  (raw: {silver.price})")
        if nickel := next((r for r in rows if r.symbol == "NICKEL"), None):
            print(f"    Nickel  = ${nickel.price:,.2f}  (raw: {nickel.price})")

        # Verify raw_json exists
        if gold:
            print(f"\n  Raw JSON for {gold.symbol}: {gold.raw_json[:80]}...")
        break  # Only one iteration needed

    # 5. Summary
    print(f"\n{'='*55}")
    if all_ok and db_total > 0:
        print(f"  [PASS] Commodity sync test PASSED")
        print(f"  Source: {'MOCK DATA' if used_mock else 'REAL API'}")
        print(f"  {db_total} records stored and verified in brsapi_commodity_prices")
        print(f"  Categories correctly classified")
        print(f"{'='*55}")
        await close_database()
        return 0
    else:
        print(f"  [FAIL] Commodity sync test FAILED")
        print(f"  Check errors above")
        print(f"{'='*55}")
        await close_database()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
