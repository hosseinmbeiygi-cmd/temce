"""
Seed database from saved BrsApi JSON response files.

Reads api_crypto_test.json and api_response_test.json, parses them
using the existing BrsApi parsers, and inserts the records into
PostgreSQL.

Usage:
    python scripts/seed_from_json.py
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
import sys
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.database import close_database, get_session, init_database
from core.logging import get_logger

logger = get_logger(__name__)

CRYPTO_FILE = Path("api_crypto_test.json")
COMMODITY_FILE = Path("api_response_test.json")


async def seed_crypto(session) -> int:
    from brsapi.models.crypto import CryptoPriceModel
    from brsapi.parsers.crypto import CryptoParser

    if not CRYPTO_FILE.exists():
        logger.warning("File not found: %s", CRYPTO_FILE)
        return 0

    raw = json.loads(CRYPTO_FILE.read_text("utf-8"))
    records = CryptoParser.parse(raw)
    if not records:
        logger.warning("No crypto records parsed")
        return 0

    await session.execute(CryptoPriceModel.__table__.delete())
    objs = [CryptoPriceModel(**r) for r in records]
    session.add_all(objs)
    await session.flush()
    logger.info("Seeded %d crypto records", len(objs))
    return len(objs)


async def seed_commodities(session) -> int:
    from brsapi.models.commodity import CommodityPriceModel
    from brsapi.parsers.commodity import CommodityParser

    if not COMMODITY_FILE.exists():
        logger.warning("File not found: %s", COMMODITY_FILE)
        return 0

    raw = json.loads(COMMODITY_FILE.read_text("utf-8"))
    records = CommodityParser.parse(raw)
    if not records:
        logger.warning("No commodity records parsed")
        return 0

    await session.execute(CommodityPriceModel.__table__.delete())
    objs = [CommodityPriceModel(**r) for r in records]
    session.add_all(objs)
    await session.flush()
    logger.info("Seeded %d commodity records", len(objs))
    return len(objs)


async def main() -> int:
    print("=" * 55)
    print("  Seed BrsApi data from saved JSON files")
    print("=" * 55)

    await init_database()

    async for session in get_session():
        total = 0

        print("\n[1/2] Seeding crypto prices...")
        try:
            c = await seed_crypto(session)
            total += c
            print(f"  [OK] {c} crypto records")
        except Exception as e:
            print(f"  [ERR] Crypto: {type(e).__name__}: {str(e)[:200]}")

        print("\n[2/2] Seeding commodity prices...")
        try:
            c = await seed_commodities(session)
            total += c
            print(f"  [OK] {c} commodity records")
        except Exception as e:
            print(f"  [ERR] Commodity: {type(e).__name__}: {str(e)[:200]}")

        break

    await close_database()

    print(f"\n{'=' * 55}")
    if total > 0:
        print(f"  [OK] Total records seeded: {total}")
    else:
        print("  [..] No records seeded (files may be missing)")
    print(f"{'=' * 55}")
    return 0


if __name__ == "__main__":
    asyncio.run(main())
