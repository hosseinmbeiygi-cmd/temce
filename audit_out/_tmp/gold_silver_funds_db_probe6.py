"""DB probe 6 (SELECT-only) — پوشش nav_records برای صندوق‌های طلای GoldDesk."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from core import database  # noqa: E402

FUND_SYMBOLS = ["عیار", "طلا", "کهربا", "زر", "زرفام", "گوهر", "تابش", "نفیس", "آلتون", "ناب"]


async def main() -> None:
    await database.init_database()
    f = database.async_session_factory
    if f is None:
        print("no db factory")
        return
    async with f() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%nav_record%'"
                )
            )
        ).all()
        print("nav tables:", [r[0] for r in rows])

        tname = "brsapi_nav_records"
        try:
            cols = (
                await s.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns WHERE table_name=:t ORDER BY ordinal_position"
                    ),
                    {"t": tname},
                )
            ).all()
            print(f"{tname} cols:", ", ".join(c[0] for c in cols))
            c = (await s.execute(text(f"SELECT COUNT(*) FROM {tname}"))).scalar()
            print(f"{tname} rows:", c)
            rows = (
                await s.execute(
                    text(
                        f"SELECT symbol, COUNT(*), MIN(date), MAX(date) FROM {tname} "
                        "WHERE symbol = ANY(:syms) GROUP BY symbol"
                    ),
                    {"syms": FUND_SYMBOLS},
                )
            ).all()
            print("gold fund symbols in nav_records:", [tuple(r) for r in rows] or "(none)")
            rows = (
                await s.execute(
                    text(
                        f"SELECT symbol, date, nav FROM {tname} "
                        "WHERE symbol = ANY(:syms) ORDER BY date DESC LIMIT 10"
                    ),
                    {"syms": FUND_SYMBOLS},
                )
            ).all()
            for r in rows:
                print("   sample:", tuple(r))
            rows = (
                await s.execute(
                    text(
                        f"SELECT symbol, COUNT(*) FROM {tname} GROUP BY symbol "
                        "ORDER BY COUNT(*) DESC LIMIT 8"
                    )
                )
            ).all()
            print("top symbols overall:", [tuple(r) for r in rows])
        except Exception as exc:
            print(f"{tname} ERROR", type(exc).__name__, str(exc)[:150])
            await s.rollback()


asyncio.run(main())
