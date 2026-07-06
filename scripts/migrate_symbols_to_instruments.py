"""Migrate all symbols from brsapi_symbol_snapshots to instruments table."""

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime

from core.database import init_database, close_database, get_session
from sqlalchemy import text


async def migrate():
    await init_database()
    count = 0
    skip = 0
    errors = 0
    async for session in get_session():
        r = await session.execute(text("SELECT count(*) FROM brsapi_symbol_snapshots"))
        total = r.scalar()
        print(f"Total symbols to migrate: {total}")

        r = await session.execute(text("SELECT symbol FROM instruments"))
        existing = {row[0] for row in r}
        print(f"Existing instruments: {len(existing)}")

        offset = 0
        batch_size = 500

        while offset < total:
            r = await session.execute(
                text("SELECT * FROM brsapi_symbol_snapshots ORDER BY id OFFSET :offset LIMIT :limit"),
                {"offset": offset, "limit": batch_size},
            )
            rows = r.fetchall()
            if not rows:
                break

            for row in rows:
                d = dict(row._mapping)
                raw_symbol = d.get("symbol", "")
                if not raw_symbol:
                    skip += 1
                    continue

                symbol = str(raw_symbol)[:50]
                if symbol in existing:
                    skip += 1
                    continue

                ins_id = str(d.get("ins_id") or "")[:50]
                sector_code = str(d.get("sector_id") or "")[:20]
                group_code = str(d.get("sector") or "")[:20]
                name = str(d.get("name") or "")[:200]
                isin = str(d.get("isin") or "")[:50] or None
                shares_count = int(d.get("shares_count") or 0)
                base_volume = int(d.get("base_volume") or 0)
                eps_val = float(d.get("eps") or 0.0)

                now = datetime.now()

                try:
                    async with session.begin_nested():
                        await session.execute(
                            text("""
                                INSERT INTO instruments
                                    (id, symbol, name, isin, market_type, asset_class, status,
                                     sector_code, group_code, shares_count, base_volume, eps,
                                     market_id, data_source, created_at, updated_at)
                                VALUES
                                    (:id, :symbol, :name, :isin, :market_type, :asset_class, :status,
                                     :sector_code, :group_code, :shares_count, :base_volume, :eps,
                                     :market_id, :data_source, :created_at, :updated_at)
                            """),
                            {
                                "id": f"inst_{ins_id or symbol}",
                                "symbol": symbol,
                                "name": name,
                                "isin": isin,
                                "market_type": "bours",
                                "asset_class": "equity",
                                "status": "active",
                                "sector_code": sector_code or None,
                                "group_code": group_code or None,
                                "shares_count": shares_count,
                                "base_volume": base_volume,
                                "eps": eps_val,
                                "market_id": ins_id or None,
                                "data_source": "brsapi",
                                "created_at": now,
                                "updated_at": None,
                            },
                        )
                    count += 1
                    existing.add(symbol)
                except Exception as exc:
                    errors += 1
                    if errors <= 5:
                        print(f"Error on {symbol}: {exc}", file=sys.stderr)

            await session.commit()
            offset += batch_size
            print(f"Migrated {count} symbols... (batch {offset // batch_size})")

        break

    await close_database()
    print(f"\nDone. Migrated {count} symbols. Skipped {skip}. Errors: {errors}")


if __name__ == "__main__":
    asyncio.run(migrate())
