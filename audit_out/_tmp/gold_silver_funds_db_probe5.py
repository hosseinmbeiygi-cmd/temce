"""DB probe 5 (SELECT-only) — قیمت انتخابی get_commodity_prices در برابر جدیدترین ردیف."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402
from core import database  # noqa: E402


async def main() -> None:
    await database.init_database()
    f = database.async_session_factory
    if f is None:
        print("no db factory")
        return
    async with f() as s:
        cols = (
            await s.execute(
                text(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_name='brsapi_commodity_prices' ORDER BY ordinal_position"
                )
            )
        ).all()
        print("cols:", ", ".join(f"{c[0]}:{c[1]}" for c in cols))

        for sym in ("XAUUSD", "XAGUSD"):
            print("=" * 70)
            print(sym)
            print("=" * 70)
            n = (
                await s.execute(
                    text(
                        "SELECT COUNT(*) FROM brsapi_commodity_prices "
                        "WHERE category='precious_metal' AND symbol=:s"
                    ),
                    {"s": sym},
                )
            ).scalar()
            print("   rows in precious_metal:", n)
            rows = (
                await s.execute(
                    text(
                        "SELECT id, price, date, time_unix FROM brsapi_commodity_prices "
                        "WHERE symbol=:s ORDER BY id DESC LIMIT 3"
                    ),
                    {"s": sym},
                )
            ).all()
            for r in rows:
                print("   by id DESC:", tuple(r))
            rows = (
                await s.execute(
                    text(
                        "SELECT id, price, date, time_unix FROM brsapi_commodity_prices "
                        "WHERE symbol=:s ORDER BY id ASC LIMIT 3"
                    ),
                    {"s": sym},
                )
            ).all()
            for r in rows:
                print("   by id ASC :", tuple(r))
            # شبیه‌سازی ترتیب get_commodity_prices: order_by(category, symbol) → آخرین ردیف هر symbol
            rows = (
                await s.execute(
                    text(
                        """
                        SELECT id, price, date, time_unix FROM brsapi_commodity_prices
                        WHERE category='precious_metal' AND symbol=:s
                        ORDER BY category, symbol LIMIT 2
                        """
                    ),
                    {"s": sym},
                )
            ).all()
            print("   first rows with ORDER BY category,symbol:", [tuple(r) for r in rows])
            rows = (
                await s.execute(
                    text(
                        """
                        SELECT id, price, date FROM brsapi_commodity_prices
                        WHERE category='precious_metal' AND symbol=:s
                        ORDER BY category, symbol LIMIT 2001
                        """
                    ),
                    {"s": sym},
                )
            ).all()
            if rows:
                print(f"   row #2001 in that order (id={rows[-1][0]}, price={rows[-1][1]}, date={rows[-1][2]})")

        print("=" * 70)
        print("سرشماری category=precious_metal")
        print("=" * 70)
        rows = (
            await s.execute(
                text(
                    "SELECT symbol, COUNT(*), MIN(date), MAX(date), COUNT(DISTINCT COALESCE(date,'')) "
                    "FROM brsapi_commodity_prices WHERE category='precious_metal' "
                    "GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 15"
                )
            )
        ).all()
        for r in rows:
            print("   ", tuple(r))

        print("=" * 70)
        print("شبیه‌سازی dict نهایی GoldDesk._read_brsapi_prices برای XAUUSD")
        print("=" * 70)
        # همان کاری که کد می‌کند: برای هر ردیف به ترتیب order_by(category,symbol) مقدار را overwrite کن
        rows = (
            await s.execute(
                text(
                    "SELECT symbol, price FROM brsapi_commodity_prices "
                    "WHERE category='precious_metal' AND symbol='XAUUSD' ORDER BY category, symbol"
                )
            )
        ).all()
        last = None
        for sym, price in rows:
            last = price
        print(f"   تعداد ردیف‌های اسکن‌شده: {len(rows)}   مقدار نهایی dict: {last}")
        newest = (
            await s.execute(
                text(
                    "SELECT price, date FROM brsapi_commodity_prices WHERE symbol='XAUUSD' "
                    "ORDER BY id DESC LIMIT 1"
                )
            )
        ).first()
        print(f"   جدیدترین ردیف (by id): price={newest[0]} date={newest[1]}")


asyncio.run(main())
