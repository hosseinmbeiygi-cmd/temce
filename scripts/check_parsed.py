import json
import sys

sys.path.insert(0, ".")
import asyncio


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        r = await s.execute(text("""
            SELECT symbol, parsed_data FROM codal_financial_statements WHERE parsed_data IS NOT NULL LIMIT 1
        """))
        row = r.fetchone()
        if row:
            data = row[1]
            print(f"Type: {type(data)}")
            d = json.loads(data) if isinstance(data, str) else data
            print(f"Keys: {list(d.keys())}")

            # Check snapshot
            snap = d.get("snapshot", {})
            print(f"\nsnapshot keys: {list(snap.keys()) if isinstance(snap, dict) else type(snap)}")
            if isinstance(snap, dict):
                for k, v in list(snap.items())[:15]:
                    print(f"  {k}: {v}")

            # Check ratios
            ratios = d.get("ratios", {})
            print(f"\nratios type: {type(ratios)}")
            if isinstance(ratios, dict):
                for k, v in list(ratios.items())[:5]:
                    if isinstance(v, dict):
                        print(f"  {k}: {list(v.keys())[:5]}")
                    else:
                        print(f"  {k}: {v}")

asyncio.run(main())
