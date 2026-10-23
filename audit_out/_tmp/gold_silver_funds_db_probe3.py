"""DB probe 3 (فقط SELECT) — داده نقره و شکل جدول funds."""

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
        print("=" * 72)
        print("A) نمادهای نقره در brsapi_symbol_snapshots")
        print("=" * 72)
        for pat in ("XAG%", "%نقره%", "%SILVER%"):
            c = (
                await s.execute(
                    text("SELECT COUNT(*) FROM brsapi_symbol_snapshots WHERE symbol ILIKE :p"),
                    {"p": pat},
                )
            ).scalar()
            print(f"   symbol ILIKE {pat!r:<12} → {c}")
        rows = (
            await s.execute(
                text(
                    "SELECT symbol, name, price_last FROM brsapi_symbol_snapshots "
                    "WHERE symbol ILIKE '%XAG%' OR name ILIKE '%نقره%' LIMIT 10"
                )
            )
        ).all()
        for r in rows:
            print("   ", tuple(r))

        print("=" * 72)
        print("B) ستون‌های جدول funds و بازارها")
        print("=" * 72)
        cols = (
            await s.execute(
                text(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_name='funds' ORDER BY ordinal_position"
                )
            )
        ).all()
        print("   cols:", ", ".join(c[0] for c in cols))
        for q in (
            "SELECT id, symbol, name, fund_type FROM funds LIMIT 5",
            "SELECT COUNT(*) FROM funds WHERE name ILIKE '%نقره%' OR symbol ILIKE '%نقره%'",
            "SELECT COUNT(*) FROM funds WHERE name ILIKE '%طلا%' OR symbol ILIKE '%طلا%'",
            "SELECT COUNT(*) FROM funds WHERE name ILIKE '%کالا%'",
            "SELECT symbol, name, fund_type, nav, price_last FROM funds WHERE name ILIKE '%نقره%' LIMIT 10",
            "SELECT COUNT(*) FROM brsapi_symbol_snapshots WHERE symbol ILIKE '%XAU%'",
        ):
            try:
                rows = (await s.execute(text(q))).all()
                print("  ", q[:80], "→", [tuple(r) for r in rows][:10])
            except Exception as exc:
                print("  ", q[:60], "ERROR", type(exc).__name__, str(exc)[:100])
                await s.rollback()

        print("=" * 72)
        print("C) gold_fund_nav / gold field در gold_snapshots برای صندوق‌ها")
        print("=" * 72)
        print("   (جدول gold_snapshots خالی است — شمارش با شرط asset_type)")
        try:
            rows = (
                await s.execute(
                    text("SELECT asset_type, COUNT(*) FROM gold_snapshots GROUP BY asset_type")
                )
            ).all()
            print("   ", rows or "(no rows)")
        except Exception as exc:
            print("   ERROR", type(exc).__name__, str(exc)[:100])
            await s.rollback()

        print("=" * 72)
        print("D) brsapi_historical_real_legal: نماد متشکل از نقره")
        print("=" * 72)
        try:
            rows = (
                await s.execute(
                    text(
                        "SELECT symbol, MIN(date), MAX(date) FROM brsapi_historical_real_legal "
                        "WHERE symbol ILIKE '%نقره%' GROUP BY symbol LIMIT 10"
                    )
                )
            ).all()
            for r in rows:
                print("   ", tuple(r))
        except Exception as exc:
            print("   ERROR", type(exc).__name__, str(exc)[:100])
            await s.rollback()


asyncio.run(main())
