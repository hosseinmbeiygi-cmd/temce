"""Import crypto_history + history_data JSON files into database.

Tables:
  - brsapi_crypto_daily_history  (new) — crypto OHLCV
  - brsapi_gold_coin_history     (existing, empty) — gold/coin OHLC
  - brsapi_gold_currency_pro_daily_history (existing, empty) — currency OHLC
"""

import asyncio
import contextlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

CRYPTO_DIR = Path("crypto_history")
HISTORY_DIR = Path("history_data")

# Symbol → table mapping
CRYPTO_TABLE = "brsapi_crypto_daily_history"
GOLD_TABLE = "brsapi_gold_coin_history"
CURRENCY_TABLE = "brsapi_gold_currency_pro_daily_history"

# Gold/coin symbols go to gold table
GOLD_SYMBOLS = {
    "IR_GOLD_18K", "IR_GOLD_24K", "IR_GOLD_MELTED",
    "IR_COIN_1G", "IR_COIN_BAHAR", "IR_COIN_EMAMI",
    "IR_COIN_HALF", "IR_COIN_QUARTER",
    "IR_PCOIN_1-1G", "IR_PCOIN_1-2G", "IR_PCOIN_1-3G", "IR_PCOIN_1-4G",
    "IR_PCOIN_1-5G", "IR_PCOIN_100MG", "IR_PCOIN_1G", "IR_PCOIN_200MG",
    "IR_PCOIN_300MG", "IR_PCOIN_400MG", "IR_PCOIN_500MG", "IR_PCOIN_600MG",
    "IR_PCOIN_700MG", "IR_PCOIN_800MG", "IR_PCOIN_900MG",
}


def parse_value(v) -> float | None:
    """Parse a value that might be string or number."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("٬", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


async def create_crypto_table(session):
    """Create brsapi_crypto_daily_history if not exists."""
    await session.execute(__import__("sqlalchemy").text(f"""
        CREATE TABLE IF NOT EXISTS {CRYPTO_TABLE} (
            id BIGSERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            date VARCHAR(20) NOT NULL,
            price_open DOUBLE PRECISION,
            price_high DOUBLE PRECISION,
            price_low DOUBLE PRECISION,
            price_close DOUBLE PRECISION,
            volume DOUBLE PRECISION,
            fetched_at VARCHAR(30),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(symbol, date)
        )
    """))
    await session.execute(__import__("sqlalchemy").text(f"""
        CREATE INDEX IF NOT EXISTS idx_crypto_hist_sym_date ON {CRYPTO_TABLE}(symbol, date)
    """))
    await session.commit()
    print(f"Table {CRYPTO_TABLE} ready")


async def import_file(session, filepath: Path, table: str, symbol_override: str | None = None):
    """Import one JSON file into a table. Returns (inserted, skipped)."""
    symbol = symbol_override or filepath.stem.replace("_history", "")

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        return 0, 0

    inserted = 0
    skipped = 0

    # Batch insert for speed
    from sqlalchemy import text

    rows = []
    for item in data:
        date = item.get("date", "")
        if not date:
            skipped += 1
            continue

        # Normalize date: 1405/05/01 → 1405-05-01
        date_norm = date.replace("/", "-")

        o = parse_value(item.get("open"))
        h = parse_value(item.get("high"))
        lo = parse_value(item.get("low"))
        c = parse_value(item.get("close"))
        v = parse_value(item.get("volume"))

        if c is None or c <= 0:
            skipped += 1
            continue

        if table == CRYPTO_TABLE:
            rows.append({
                "symbol": symbol, "date": date_norm,
                "price_open": o, "price_high": h, "price_low": lo, "price_close": c,
                "volume": v,
            })
        elif table in (GOLD_TABLE, CURRENCY_TABLE):
            rows.append({
                "symbol": symbol, "date": date_norm,
                "price_open": o, "price_high": h, "price_low": lo, "price_close": c,
            })

    # Batch upsert
    if table == CRYPTO_TABLE:
        for row in rows:
            try:
                await session.execute(text(f"""
                    INSERT INTO {CRYPTO_TABLE} (symbol, date, price_open, price_high, price_low, price_close, volume)
                    VALUES (:symbol, :date, :price_open, :price_high, :price_low, :price_close, :volume)
                    ON CONFLICT (symbol, date) DO UPDATE SET
                        price_open = EXCLUDED.price_open,
                        price_high = EXCLUDED.price_high,
                        price_low = EXCLUDED.price_low,
                        price_close = EXCLUDED.price_close,
                        volume = EXCLUDED.volume
                """), row)
                inserted += 1
            except Exception:
                skipped += 1
    elif table == GOLD_TABLE:
        for row in rows:
            try:
                await session.execute(text(f"""
                    INSERT INTO {GOLD_TABLE} (symbol, date, price_open, price_high, price_low, price_close)
                    VALUES (:symbol, :date, :price_open, :price_high, :price_low, :price_close)
                    ON CONFLICT (symbol, date) DO UPDATE SET
                        price_open = EXCLUDED.price_open,
                        price_high = EXCLUDED.price_high,
                        price_low = EXCLUDED.price_low,
                        price_close = EXCLUDED.price_close
                """), row)
                inserted += 1
            except Exception:
                skipped += 1
    elif table == CURRENCY_TABLE:
        for row in rows:
            try:
                await session.execute(text(f"""
                    INSERT INTO {CURRENCY_TABLE} (symbol, date, price_open, price_high, price_low, price_close)
                    VALUES (:symbol, :date, :price_open, :price_high, :price_low, :price_close)
                    ON CONFLICT (symbol, date) DO UPDATE SET
                        price_open = EXCLUDED.price_open,
                        price_high = EXCLUDED.price_high,
                        price_low = EXCLUDED.price_low,
                        price_close = EXCLUDED.price_close
                """), row)
                inserted += 1
            except Exception:
                skipped += 1

    await session.commit()
    return inserted, skipped


async def main():
    from core.database import init_database
    await init_database()

    from core.database import async_session_factory

    total_inserted = 0
    total_skipped = 0
    start = time.time()

    async with async_session_factory() as session:
        # 1. Create crypto table
        await create_crypto_table(session)

        # 2. Import crypto_history
        print("\n=== Crypto History ===")
        crypto_files = sorted(CRYPTO_DIR.glob("*.json"))
        for fp in crypto_files:
            ins, skip = await import_file(session, fp, CRYPTO_TABLE)
            total_inserted += ins
            total_skipped += skip
            print(f"  {fp.stem}: +{ins} rows ({skip} skipped)")

        # 3. Import history_data
        print("\n=== History Data ===")
        history_files = sorted(HISTORY_DIR.glob("*.json"))
        for fp in history_files:
            symbol = fp.stem.replace("_history", "")
            table = GOLD_TABLE if symbol in GOLD_SYMBOLS else CURRENCY_TABLE

            ins, skip = await import_file(session, fp, table)
            total_inserted += ins
            total_skipped += skip
            target = "GOLD" if table == GOLD_TABLE else "CURRENCY"
            print(f"  {fp.stem} → {target}: +{ins} rows ({skip} skipped)")

    elapsed = time.time() - start
    print("\n=== DONE ===")
    print(f"Inserted: {total_inserted:,} rows")
    print(f"Skipped: {total_skipped:,} rows")
    print(f"Time: {elapsed:.1f}s")

    # Final counts
    async with async_session_factory() as session:
        from sqlalchemy import text
        for t in [CRYPTO_TABLE, GOLD_TABLE, CURRENCY_TABLE]:
            with contextlib.suppress(Exception):
                r = await session.execute(text(f"SELECT COUNT(*) FROM {t}"))
                print(f"  {t}: {r.scalar():,} rows")


if __name__ == "__main__":
    asyncio.run(main())
